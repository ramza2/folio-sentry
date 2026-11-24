"""One-shot synthetic MD-03 PostgreSQL CI integration test.

Runs ONLY on dedicated GitHub Actions ephemeral database after Alembic upgrade.
No network to KIS, no real assets, no production DB. All DML is rolled back.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.portfolio_models import Instrument
from app.price_models import PriceBar
from app.price_repository import (
    PriceBarStorageError, insert_unverified_daily_batch,
)

if not (
    os.environ.get("FOLIOSENTRY_MD03_ISOLATED_DB_TEST") == "yes"
    and os.environ.get("FOLIOSENTRY_DB_HOST") == "127.0.0.1"
    and os.environ.get("FOLIOSENTRY_DB_NAME") == "folio_ci"
    and os.environ.get("FOLIOSENTRY_DB_USER") == "folio_ci"
):
    raise SystemExit("MD03_ISOLATED_CI_GUARD_REQUIRED")

identity = InstrumentIdentity("KR", "XKRX", "000001", "KRW")
fetched = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
sample = {
    "stck_bsop_date": "20261119", "stck_oprc": "100",
    "stck_hgpr": "110", "stck_lwpr": "90",
    "stck_clpr": "105", "acml_vol": "123456",
}
batch = normalize_kis_daily_response(
    {"rt_cd": "0", "output2": [sample]}, identity=identity,
    price_basis="RAW", fetched_at=fetched,
)
now = fetched + timedelta(minutes=1)

with Session(get_engine()) as db:
    try:
        instrument = Instrument(
            market="KR", exchange_mic="XKRX", symbol="000001",
            normalized_symbol="000001", name="MD03 synthetic only",
            currency="KRW", asset_type="STOCK", timezone="Asia/Seoul",
        )
        db.add(instrument)
        db.flush()
        try:
            insert_unverified_daily_batch(db, instrument.id, batch, now=now)
        except PriceBarStorageError as exc:
            assert str(exc) == "PRICE_BAR_WRITE_DISABLED"
        else:
            raise AssertionError("must reject default write")

        first = insert_unverified_daily_batch(
            db, instrument.id, batch, now=now, allow_write=True,
        )
        assert (first.inserted, first.unchanged) == (1, 0)
        again = insert_unverified_daily_batch(
            db, instrument.id, batch, now=now, allow_write=True,
        )
        assert (again.inserted, again.unchanged) == (0, 1)
        stored = db.scalars(select(PriceBar)).one()
        assert stored.close == 105
        assert stored.is_final is False
        assert stored.quality_status == "PARTIAL"
        assert stored.source_observed_at is None

        modified = replace(batch, bars=(
            replace(batch.bars[0], close=batch.bars[0].close + 1),
        ))
        try:
            with db.begin_nested():
                insert_unverified_daily_batch(
                    db, instrument.id, modified, now=now, allow_write=True,
                )
        except PriceBarStorageError as exc:
            assert str(exc) == "PRICE_BAR_CONFLICT_NEEDS_REVIEW"
        else:
            raise AssertionError("conflicting prices must not be overwritten")
        assert db.scalars(select(PriceBar)).one().close == 105

        # Reproduce a dangerous batch: first item would INSERT, second item
        # conflicts with existing RAW price. Catch WITHOUT external savepoint.
        # Repository-owned savepoint must roll back first item, even if caller
        # catches and continues its surrounding transaction.
        new_adjusted = replace(batch.bars[0], price_basis="ADJUSTED")
        conflicting_raw = replace(batch.bars[0], close=batch.bars[0].close + 1)
        partial_batch = replace(batch, bars=(new_adjusted, conflicting_raw))
        try:
            insert_unverified_daily_batch(
                db, instrument.id, partial_batch, now=now, allow_write=True,
            )
        except PriceBarStorageError as exc:
            assert str(exc) == "PRICE_BAR_CONFLICT_NEEDS_REVIEW"
        else:
            raise AssertionError("multi-bar partial write must fail atomically")
        assert db.scalar(select(func.count()).select_from(PriceBar)) == 1
        assert db.scalars(select(PriceBar)).one().price_basis == "RAW"
        print("FOLIOSENTRY_MD03_BATCH_SAVEPOINT_ATOMICITY_PASS")

        try:
            with db.begin_nested():
                db.execute(
                    update(PriceBar).where(PriceBar.id == stored.id)
                    .values(is_final=True, quality_status="VALID")
                )
                db.flush()
        except IntegrityError:
            pass
        else:
            raise AssertionError("database must reject final/VALID promotion")

        assert db.scalar(select(func.count()).select_from(PriceBar)) == 1
        print("FOLIOSENTRY_MD03_ISOLATED_INSERT_DUPLICATE_CONFLICT_FINALITY_PASS")
    finally:
        db.rollback()

with Session(get_engine()) as db:
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 0
    assert db.scalar(
        select(func.count()).select_from(Instrument)
        .where(Instrument.normalized_symbol == "000001")
    ) == 0
print("FOLIOSENTRY_MD03_ISOLATED_ROLLBACK_PASS")


# MD-04A: entirely synthetic KR + US KIS transport -> normalization -> strict
# intake gate -> PARTIAL-only repository. Both instruments and rows rollback.
# The injected callable is the ONLY transport used. It cannot call KIS/Internet.
from datetime import date
from itertools import count

from app.kis_readonly import (
    KR_DAILY_PATH, US_DAILY_PATH, TOKEN_PATH,
    KisCredentials, KisReadOnlyDailyProvider,
)
from app.md04_intake import inspect_unverified_intake

us_identity = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
us_row = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}
synthetic_calls: list[tuple[str, str]] = []


def synthetic_transport(method, path, headers, params=None, body=None):
    synthetic_calls.append((method, path))
    if (method, path) == ("POST", TOKEN_PATH):
        assert body and body["grant_type"] == "client_credentials"
        return {"access_token": "synthetic-token-no-real-credentials-123",
                "expires_in": 3600}
    assert method == "GET" and body is None
    if path == KR_DAILY_PATH:
        return {"rt_cd": "0", "output2": [sample]}
    if path == US_DAILY_PATH:
        return {"rt_cd": "0", "output2": [us_row]}
    raise AssertionError("UNEXPECTED_SYNTHETIC_TRANSPORT_PATH")


# The provider's explicit live flag is used only in this synthetic guarded CI
# script, with a fake injected callable: NO live network implementation.
fake_clock = count(1000, 2)
provider = KisReadOnlyDailyProvider(
    KisCredentials("synthetic-appkey-for-ci", "synthetic-secret-for-ci"),
    live_enabled=True, transport=synthetic_transport,
    monotonic=lambda: next(fake_clock), utcnow=lambda: fetched,
)
kr_batch = provider.fetch_daily(
    identity, date(2026, 11, 19), date(2026, 11, 19), "RAW",
)
us_batch = provider.fetch_daily(
    us_identity, date(2026, 11, 19), date(2026, 11, 19), "RAW",
)
for expected, candidate in ((identity, kr_batch), (us_identity, us_batch)):
    receipt = inspect_unverified_intake(expected, candidate, now=now)
    assert receipt.accepted_rows == 1
    assert receipt.quality_status == "PARTIAL"
    assert receipt.availability == "UNFINALIZED"
    assert receipt.is_final is False and receipt.publication_allowed is False
    assert receipt.automatic_storage_allowed is False
assert synthetic_calls == [
    ("POST", TOKEN_PATH), ("GET", KR_DAILY_PATH), ("GET", US_DAILY_PATH)
]

with Session(get_engine()) as db:
    try:
        for candidate_identity, candidate in (
            (identity, kr_batch), (us_identity, us_batch),
        ):
            instrument = Instrument(
                market=candidate_identity.market,
                exchange_mic=candidate_identity.exchange_mic,
                symbol=candidate_identity.symbol,
                normalized_symbol=candidate_identity.symbol,
                name="MD04A synthetic only",
                currency=candidate_identity.currency,
                asset_type="STOCK",
                timezone=str(candidate_identity.exchange_timezone),
            )
            db.add(instrument)
            db.flush()
            inserted = insert_unverified_daily_batch(
                db, instrument.id, candidate, now=now, allow_write=True,
            )
            assert (inserted.inserted, inserted.unchanged) == (1, 0)
        saved = db.scalars(select(PriceBar)).all()
        assert len(saved) == 2
        assert all(item.quality_status == "PARTIAL" and
                   item.is_final is False and
                   item.source_observed_at is None for item in saved)
        print("FOLIOSENTRY_MD04A_SYNTHETIC_KIS_TO_ISOLATED_DB_PASS")
    finally:
        db.rollback()

with Session(get_engine()) as db:
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 0
    for symbol in (identity.symbol, us_identity.symbol):
        assert db.scalar(
            select(func.count()).select_from(Instrument)
            .where(Instrument.normalized_symbol == symbol)
        ) == 0
print("FOLIOSENTRY_MD04A_ROLLBACK_AND_NONPUBLICATION_PASS")


# MD06 reference-only storage on a date outside the attested whitelist.
# Same PARTIAL schema; no live network, no finality promotion, rollback.
from app.price_repository import insert_reference_daily_batch
from app.price_quality import PriceBarQualityError

reference_identity = InstrumentIdentity("KR", "XKRX", "000006", "KRW")
reference_fetch = datetime(2026, 11, 24, 0, tzinfo=timezone.utc)
reference_batch = normalize_kis_daily_response(
    {"rt_cd": "0", "output2": [dict(sample, stck_bsop_date="20261123")]},
    identity=reference_identity, price_basis="RAW", fetched_at=reference_fetch,
)
with Session(get_engine()) as db:
    try:
        instrument = Instrument(
            market="KR", exchange_mic="XKRX", symbol="000006",
            normalized_symbol="000006", name="MD06 synthetic only",
            currency="KRW", asset_type="STOCK", timezone="Asia/Seoul",
        )
        db.add(instrument)
        db.flush()
        try:
            insert_unverified_daily_batch(db, instrument.id, reference_batch,
                                          now=reference_fetch, allow_write=True)
        except PriceBarQualityError as exc:
            assert str(exc) == "PRICE_SESSION_CALENDAR_UNVERIFIED"
        else:
            raise AssertionError("strict attested policy must remain unchanged")
        result = insert_reference_daily_batch(db, instrument.id, reference_batch,
                                             now=reference_fetch, allow_write=True)
        assert (result.inserted, result.unchanged) == (1, 0)
        again = insert_reference_daily_batch(db, instrument.id, reference_batch,
                                            now=reference_fetch, allow_write=True)
        assert (again.inserted, again.unchanged) == (0, 1)
        row = db.scalars(select(PriceBar).where(PriceBar.instrument_id == instrument.id)).one()
        assert row.quality_status == "PARTIAL" and row.is_final is False
        assert row.source_observed_at is None
        changed = replace(reference_batch, bars=(
            replace(reference_batch.bars[0], close=reference_batch.bars[0].close + 1),
        ))
        try:
            insert_reference_daily_batch(db, instrument.id, changed,
                                         now=reference_fetch, allow_write=True)
        except PriceBarStorageError as exc:
            assert str(exc) == "PRICE_BAR_CONFLICT_NEEDS_REVIEW"
        else:
            raise AssertionError("reference correction must not overwrite first observation")
    finally:
        db.rollback()
print("FOLIOSENTRY_MD06_REFERENCE_STORAGE_POSTGRES_PASS")

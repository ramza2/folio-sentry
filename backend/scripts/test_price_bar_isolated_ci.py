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

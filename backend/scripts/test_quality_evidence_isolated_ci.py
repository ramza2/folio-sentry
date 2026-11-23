"""MD-04C3 synthetic quality-evidence PostgreSQL CI only.

Isolated folio_ci loopback database only. No real prices/accounts/KIS,
no API, no scheduler. All synthetic rows rolled back.
"""
from datetime import date, datetime, timedelta, timezone
import os

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.md04_finality import review_daily_finality_gaps, UNVERIFIED_REASONS
from app.portfolio_models import Instrument
from app.price_models import PriceBar
from app.price_repository import insert_unverified_daily_batch
from app.quality_evidence_models import PriceQualityEvidence
from app.quality_evidence_repository import (
    QualityEvidenceStorageError, insert_unverified_evidence,
)

if not (
    os.environ.get("FOLIOSENTRY_MD04C3_ISOLATED_DB_TEST") == "yes"
    and os.environ.get("FOLIOSENTRY_DB_HOST") == "127.0.0.1"
    and os.environ.get("FOLIOSENTRY_DB_NAME") == "folio_ci"
    and os.environ.get("FOLIOSENTRY_DB_USER") == "folio_ci"
):
    raise SystemExit("MD04C3_ISOLATED_CI_GUARD_REQUIRED")

fetched = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
reviewed = fetched + timedelta(minutes=1)
sample = {
    "stck_bsop_date": "20261119", "stck_oprc": "100",
    "stck_hgpr": "110", "stck_lwpr": "90",
    "stck_clpr": "105", "acml_vol": "123456",
}
us_sample = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}
identities = [
    InstrumentIdentity("KR", "XKRX", "009999", "KRW"),
    InstrumentIdentity("US", "XNAS", "ZXYY", "USD"),
]

with Session(get_engine()) as db:
    try:
        for identity in identities:
            payload = {"rt_cd": "0", "output2": [
                sample if identity.market == "KR" else us_sample
            ]}
            batch = normalize_kis_daily_response(
                payload, identity=identity, price_basis="RAW", fetched_at=fetched,
            )
            evidence = review_daily_finality_gaps(
                identity, batch, requested_basis="RAW", now=reviewed,
            )
            assert evidence.availability == "UNFINALIZED"
            inst = Instrument(
                market=identity.market, exchange_mic=identity.exchange_mic,
                symbol=identity.symbol, normalized_symbol=identity.symbol,
                name="MD04C3 synthetic-only",
                currency=identity.currency, asset_type="STOCK",
                timezone=str(identity.exchange_timezone),
            )
            db.add(inst)
            db.flush()
            insert_unverified_daily_batch(
                db, inst.id, batch, now=reviewed, allow_write=True,
            )
            bar = db.scalars(
                select(PriceBar).where(PriceBar.instrument_id == inst.id)
            ).one()
            try:
                insert_unverified_evidence(
                    db, bar.id, evidence, reviewed_at=reviewed,
                )
            except QualityEvidenceStorageError as exc:
                assert str(exc) == "QUALITY_EVIDENCE_WRITE_DISABLED"
            else:
                raise AssertionError("missing opt-in must not store evidence")

            first = insert_unverified_evidence(
                db, bar.id, evidence, reviewed_at=reviewed,
                allow_write=True,
            )
            again = insert_unverified_evidence(
                db, bar.id, evidence,
                reviewed_at=reviewed + timedelta(minutes=2),
                allow_write=True,
            )
            assert (first.inserted, first.unchanged) == (1, 0)
            assert (again.inserted, again.unchanged) == (0, 1)
            snapshot = db.scalars(
                select(PriceQualityEvidence)
                .where(PriceQualityEvidence.price_bar_id == bar.id)
            ).one()
            assert snapshot.reviewed_at == reviewed
            assert snapshot.evidence_status == "UNVERIFIED"
            assert snapshot.provider_finality == "UNATTESTED"
            assert snapshot.source_observed_at is None
            assert snapshot.blocker_codes == list(UNVERIFIED_REASONS)
            assert snapshot.is_final is False
            assert snapshot.publication_allowed is False
            assert snapshot.analysis_allowed is False

            # An existing contradictory evidence record must cause a
            # conflict, never an unreviewed overwrite of prior history.
            snapshot.blocker_codes = ["UNTRUSTED"]
            db.flush()
            try:
                insert_unverified_evidence(
                    db, bar.id, evidence, reviewed_at=reviewed,
                    allow_write=True,
                )
            except QualityEvidenceStorageError as exc:
                assert str(exc) == "QUALITY_EVIDENCE_CONFLICT_NEEDS_REVIEW"
            else:
                raise AssertionError("conflicting evidence must be denied")
            snapshot.blocker_codes = list(UNVERIFIED_REASONS)
            db.flush()

            for prohibited in (
                {"is_final": True},
                {"publication_allowed": True},
                {"analysis_allowed": True},
                {"provider_finality": "FINAL"},
                {"evidence_status": "VERIFIED"},
                {"source_observed_at": reviewed},
                {"basis_attested": True},
            ):
                try:
                    with db.begin_nested():
                        db.execute(
                            update(PriceQualityEvidence)
                            .where(PriceQualityEvidence.id == snapshot.id)
                            .values(**prohibited)
                        )
                        db.flush()
                except IntegrityError:
                    pass
                else:
                    raise AssertionError("DB must reject unsupported evidence claim")
            assert db.get(PriceBar, bar.id).quality_status == "PARTIAL"
            assert db.get(PriceBar, bar.id).is_final is False

        assert db.scalar(select(func.count()).select_from(PriceQualityEvidence)) == 2
        print("FOLIOSENTRY_MD04C3_ISOLATED_METADATA_CONSTRAINTS_PASS")
    finally:
        db.rollback()

with Session(get_engine()) as db:
    assert db.scalar(select(func.count()).select_from(PriceQualityEvidence)) == 0
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 0
    for identity in identities:
        assert db.scalar(
            select(func.count()).select_from(Instrument)
            .where(Instrument.normalized_symbol == identity.symbol)
        ) == 0
print("FOLIOSENTRY_MD04C3_ISOLATED_ROLLBACK_NONPUBLICATION_PASS")

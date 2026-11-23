"""MD-04C4 synthetic source reference revision tests on isolated PostgreSQL.

No real documents, quotes, credentials, network, production DB, or approvals.
All data is rolled back. CI host/user/database gate required.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import os

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.evidence_reference_models import EvidenceReferenceRevision
from app.evidence_reference_repository import (
    EvidenceReferenceError, append_unverified_reference, verify_reference_chain,
)
from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.md04_finality import review_daily_finality_gaps
from app.portfolio_models import Instrument
from app.price_models import PriceBar
from app.price_repository import insert_unverified_daily_batch
from app.quality_evidence_models import PriceQualityEvidence
from app.quality_evidence_repository import insert_unverified_evidence

if not (
    os.environ.get("FOLIOSENTRY_MD04C4_ISOLATED_DB_TEST") == "yes"
    and os.environ.get("FOLIOSENTRY_DB_HOST") == "127.0.0.1"
    and os.environ.get("FOLIOSENTRY_DB_NAME") == "folio_ci"
    and os.environ.get("FOLIOSENTRY_DB_USER") == "folio_ci"
):
    raise SystemExit("MD04C4_ISOLATED_CI_GUARD_REQUIRED")

identity = InstrumentIdentity("KR", "XKRX", "009998", "KRW")
fetched = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
reviewed = fetched + timedelta(minutes=1)
sample = {
    "stck_bsop_date": "20261119", "stck_oprc": "100", "stck_hgpr": "110",
    "stck_lwpr": "90", "stck_clpr": "105", "acml_vol": "123456",
}
batch = normalize_kis_daily_response(
    {"rt_cd": "0", "output2": [sample]},
    identity=identity, price_basis="RAW", fetched_at=fetched,
)
report = review_daily_finality_gaps(identity, batch, requested_basis="RAW", now=reviewed)
assert report.is_final is False and report.publication_allowed is False
digest1 = hashlib.sha256(b"synthetic-doc-v1").hexdigest()
digest2 = hashlib.sha256(b"synthetic-doc-v2").hexdigest()
digest3 = hashlib.sha256(b"synthetic-retraction-note").hexdigest()
url1 = "https://apiportal.koreainvestment.com/apiservice"
url2 = "https://github.com/koreainvestment/open-trading-api/tree/main"

with Session(get_engine()) as db:
    try:
        inst = Instrument(
            market="KR", exchange_mic="XKRX", symbol=identity.symbol,
            normalized_symbol=identity.symbol, name="MD04C4 synthetic only",
            currency="KRW", asset_type="STOCK", timezone="Asia/Seoul",
        )
        db.add(inst)
        db.flush()
        insert_unverified_daily_batch(
            db, inst.id, batch, now=reviewed, allow_write=True
        )
        bar = db.scalars(select(PriceBar).where(PriceBar.instrument_id == inst.id)).one()
        insert_unverified_evidence(
            db, bar.id, report, reviewed_at=reviewed, allow_write=True
        )
        audit = db.scalars(
            select(PriceQualityEvidence)
            .where(PriceQualityEvidence.price_bar_id == bar.id)
        ).one()
        one = dict(
            revision_no=1, event_type="RECORDED",
            source_kind="KIS_DOCUMENT", reference_url=url1,
            document_version="v1", document_sha256=digest1,
            recorded_at=reviewed + timedelta(minutes=1),
        )
        try:
            append_unverified_reference(db, audit.id, **one)
        except EvidenceReferenceError as exc:
            assert str(exc) == "REFERENCE_WRITE_DISABLED"
        else:
            raise AssertionError("write without opt-in must fail")
        first = append_unverified_reference(
            db, audit.id, **one, allow_write=True
        )
        again = append_unverified_reference(
            db, audit.id, **one, allow_write=True
        )
        assert (first.inserted, first.unchanged) == (1, 0)
        assert (again.inserted, again.unchanged) == (0, 1)
        assert first.event_sha256 == again.event_sha256

        conflict = dict(one, document_sha256=digest2)
        try:
            append_unverified_reference(
                db, audit.id, **conflict, allow_write=True
            )
        except EvidenceReferenceError as exc:
            assert str(exc) == "REFERENCE_REVISION_CONFLICT"
        else:
            raise AssertionError("revision conflict must not overwrite")
        corrected = dict(
            one, revision_no=2, event_type="CORRECTED",
            reference_url=url2, document_version="v2",
            document_sha256=digest2,
            recorded_at=one["recorded_at"] + timedelta(minutes=1),
        )
        second = append_unverified_reference(
            db, audit.id, **corrected, allow_write=True
        )
        assert second.inserted == 1
        retraction = dict(
            corrected, revision_no=3, event_type="RETRACTED",
            document_version="v3", document_sha256=digest3,
            recorded_at=corrected["recorded_at"] + timedelta(minutes=1),
        )
        third = append_unverified_reference(
            db, audit.id, **retraction, allow_write=True
        )
        assert third.inserted == 1
        for attempted in (
            dict(one, revision_no=3, event_type="CORRECTED"),
            dict(retraction, revision_no=4, event_type="CORRECTED",
                 recorded_at=retraction["recorded_at"] + timedelta(minutes=1)),
            dict(retraction, revision_no=5, event_type="RETRACTED"),
        ):
            try:
                append_unverified_reference(
                    db, audit.id, **attempted, allow_write=True
                )
            except EvidenceReferenceError:
                pass
            else:
                raise AssertionError("correction gap or retraction bypass must fail")

        events = db.scalars(
            select(EvidenceReferenceRevision)
            .where(EvidenceReferenceRevision.quality_evidence_id == audit.id)
            .order_by(EvidenceReferenceRevision.revision_no)
        ).all()
        assert [event.revision_no for event in events] == [1, 2, 3]
        assert verify_reference_chain(list(events))
        assert events[1].previous_event_sha256 == first.event_sha256
        assert events[2].previous_event_sha256 == second.event_sha256
        assert all(
            e.verification_status == "UNVERIFIED_REFERENCE"
            and e.publication_allowed is False for e in events
        )
        # PostgreSQL trigger blocks ordinary UPDATE and DELETE; no
        # history rewrite, even for nonprice metadata.
        for statement in (
            update(EvidenceReferenceRevision)
                .where(EvidenceReferenceRevision.id == events[0].id)
                .values(document_version="forged"),
            delete(EvidenceReferenceRevision)
                .where(EvidenceReferenceRevision.id == events[0].id),
        ):
            try:
                with db.begin_nested():
                    db.execute(statement)
                    db.flush()
            except DBAPIError:
                pass
            else:
                raise AssertionError("append-only trigger must reject mutations")

        # DB CHECK prevents bypassing the unverified/publication restriction.
        try:
            with db.begin_nested():
                db.add(EvidenceReferenceRevision(
                    quality_evidence_id=audit.id,
                    revision_no=4, event_type="CORRECTED",
                    source_kind="KIS_DOCUMENT", reference_url=url1,
                    document_version="v4", document_sha256=digest1,
                    recorded_at=retraction["recorded_at"] + timedelta(minutes=1),
                    previous_event_sha256=third.event_sha256,
                    event_sha256="0" * 64,
                    verification_status="VERIFIED",
                    publication_allowed=True,
                ))
                db.flush()
        except DBAPIError:
            pass
        else:
            raise AssertionError("DB must forbid forged verification/publication")

        assert db.scalar(
            select(func.count()).select_from(EvidenceReferenceRevision)
        ) == 3
        assert db.get(PriceBar, bar.id).quality_status == "PARTIAL"
        assert db.get(PriceBar, bar.id).is_final is False
        assert db.get(PriceQualityEvidence, audit.id).publication_allowed is False
        print("FOLIOSENTRY_MD04C4_ISOLATED_REFERENCES_CHAIN_IMMUTABLE_PASS")
    finally:
        db.rollback()

with Session(get_engine()) as db:
    assert db.scalar(select(func.count()).select_from(EvidenceReferenceRevision)) == 0
    assert db.scalar(select(func.count()).select_from(PriceQualityEvidence)) == 0
    assert db.scalar(select(func.count()).select_from(PriceBar)) == 0
    assert db.scalar(select(func.count()).select_from(Instrument)
        .where(Instrument.normalized_symbol == identity.symbol)) == 0
print("FOLIOSENTRY_MD04C4_ISOLATED_ROLLBACK_NONPUBLICATION_PASS")

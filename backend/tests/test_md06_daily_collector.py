"""MD06 synthetic collector tests; no actual credentials, DB or KIS calls."""
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.market_data import InstrumentIdentity, DailyBarCandidate, DailyBarBatch
from app.md06_daily_collector import (
    Target, collection_window, reserve_run, run_collection, main,
    CollectionError, MAX_TARGETS,
)
from app.price_quality import (
    validate_reference_batch, validate_batch, PriceBarQualityError,
)

NOW = datetime(2026, 11, 24, 0, tzinfo=timezone.utc)
KR = InstrumentIdentity("KR", "XKRX", "000001", "KRW")


def batch(identity=KR, day=date(2026, 11, 23)):
    return DailyBarBatch(identity, (DailyBarCandidate(
        session_date=day, open=Decimal("100"), high=Decimal("110"),
        low=Decimal("90"), close=Decimal("105"), volume=123,
        price_basis="RAW", source="KIS", fetched_at=NOW,
    ),))


def test_prior_market_dates_and_dst():
    assert collection_window("KR", NOW) == (
        date(2026, 11, 24), date(2026, 8, 26), date(2026, 11, 23))
    assert collection_window("US", NOW) is None
    for instant in (datetime(2026, 11, 24, 12, tzinfo=timezone.utc),
                    datetime(2026, 7, 14, 11, tzinfo=timezone.utc)):
        assert collection_window("US", instant)[2] == instant.date().replace(day=instant.day-1)
    assert collection_window("KR", datetime(2026, 11, 23, 0, tzinfo=timezone.utc)) is None
    assert collection_window("KR", datetime(2026, 11, 28, 0, tzinfo=timezone.utc))[2] == date(2026, 11, 27)
    with pytest.raises(CollectionError):
        collection_window("KR", datetime(2026, 11, 24))


def test_reference_history_not_attested_or_final():
    candidate = batch()
    with pytest.raises(PriceBarQualityError, match="CALENDAR_UNVERIFIED"):
        validate_batch(candidate, now=NOW)
    stored = validate_reference_batch(candidate, now=NOW)[0]
    assert stored.quality_status == "PARTIAL" and not stored.is_final
    assert stored.source_observed_at is None


@pytest.mark.parametrize("changes", [
    {"session_date": date(2026, 11, 24)},
    {"session_date": date(2026, 11, 22)},
    {"price_basis": "ADJUSTED"}, {"is_final": True},
    {"low": Decimal("200")}, {"volume": -1},
])
def test_invalid_reference_rejected(changes):
    b = batch()
    with pytest.raises(PriceBarQualityError):
        validate_reference_batch(replace(b, bars=(replace(b.bars[0], **changes),)), now=NOW)


def test_runner_success_and_no_repeat(tmp_path):
    state = tmp_path / "private"
    state.mkdir(mode=0o700)
    targets = tuple(Target(uuid4(), KR) for _ in range(2))
    calls, pauses = [], []
    def fetch(identity, start, end, basis):
        assert identity == KR and end == date(2026, 11, 23) and basis == "RAW"
        calls.append(identity)
        return batch()
    args = dict(clock=lambda: NOW, list_targets=lambda m: targets,
                provider_factory=lambda: SimpleNamespace(fetch_daily=fetch),
                store=lambda t,b,n: SimpleNamespace(inserted=1, unchanged=0),
                state_dir=state, sleep=pauses.append)
    assert run_collection("KR", **args) == ("COMPLETE", 2, 2, 0, 0)
    assert pauses == [2.0]
    assert run_collection("KR", **args)[0] == "ALREADY_ATTEMPTED_OR_BUSY"
    assert len(calls) == 2


def test_failure_no_retry(tmp_path):
    state = tmp_path / "private"
    state.mkdir(mode=0o700)
    calls = []
    def fetch(*args):
        calls.append(1)
        raise RuntimeError("synthetic private upstream detail")
    args = dict(clock=lambda: NOW, list_targets=lambda m: (Target(uuid4(), KR),),
                provider_factory=lambda: SimpleNamespace(fetch_daily=fetch),
                store=lambda *args: pytest.fail("must not store"),
                state_dir=state)
    assert run_collection("KR", **args) == ("STOPPED_ON_ERROR", 1, 0, 0, 0)
    assert run_collection("KR", **args)[0] == "ALREADY_ATTEMPTED_OR_BUSY"
    assert calls == [1]


def test_lock_and_limit(tmp_path):
    state = tmp_path / "private"
    state.mkdir(mode=0o700)
    with reserve_run(state, "KR", NOW.date()) as first:
        assert first
        with reserve_run(state, "US", NOW.date()) as second:
            assert not second
    with pytest.raises(CollectionError, match="LIMIT"):
        run_collection("KR", clock=lambda: NOW,
                       list_targets=lambda m: tuple(Target(uuid4(), KR) for _ in range(MAX_TARGETS+1)),
                       provider_factory=lambda: pytest.fail("must not call"),
                       store=lambda *args: pytest.fail("must not store"), state_dir=state)


def test_default_off_before_db(monkeypatch):
    import app.md06_daily_collector as module
    monkeypatch.delenv("FOLIOSENTRY_MD06_AUTO_COLLECT_ENABLED", raising=False)
    monkeypatch.setattr(module, "get_engine", lambda: pytest.fail("must not open DB"))
    assert main(["--market", "KR", "--confirm-reference-collection"]) == 2

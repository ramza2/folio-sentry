"""MD-02D shared token/quote gate: synthetic transport only, zero KIS requests."""
from datetime import date, datetime, timezone
import json
import os

import pytest

from app.kis_readonly import (
    KR_DAILY_PATH, US_DAILY_PATH, TOKEN_PATH, KisCredentials,
    KisReadOnlyDailyProvider, KisReadOnlyError,
)
from app.kis_shared_state import (
    KisSharedState, KisSharedStateError, LOCK_FILE, STATE_FILE,
    MIN_TOKEN_ISSUE_GAP, MAX_HTTP_REQUESTS_24H,
)
from app.market_data import InstrumentIdentity


KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
DAY = date(2026, 11, 19)
NOW = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
KEY = KisCredentials("synthetic-appkey", "synthetic-appsecret")
KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "70000", "stck_hgpr": "72000",
    "stck_lwpr": "69000", "stck_clpr": "71000", "acml_vol": "12345678",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}


class Clock:
    def __init__(self):
        self.value = NOW.timestamp()

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class Stub:
    def __init__(self, *, ttl=86400, fail_token=False, fail_quote=False):
        self.calls = []
        self.ttl = ttl
        self.fail_token = fail_token
        self.fail_quote = fail_quote

    def __call__(self, method, path, headers, params=None, body=None):
        self.calls.append((method, path))
        if path == TOKEN_PATH:
            if self.fail_token:
                raise RuntimeError("PRIVATE synthetic upstream error never print")
            return {"access_token": "synthetic-token-123456", "expires_in": self.ttl}
        if self.fail_quote:
            raise RuntimeError("PRIVATE synthetic quote error never print")
        return {"rt_cd": "0", "output2": [
            KR_ROW if path == KR_DAILY_PATH else US_ROW
        ]}


def state(tmp_path, clock):
    path = tmp_path / "state"
    path.mkdir(mode=0o700)
    return KisSharedState(path, clock=clock), path


def cli(gate, stub, *, enabled=True, issue=False):
    return KisReadOnlyDailyProvider(
        KEY, transport=stub, shared_state=gate,
        allow_shared_token_issue=issue, live_enabled=enabled,
        utcnow=lambda: NOW,
    )


def fetch(client, identity=KR):
    return client.fetch_daily(identity, DAY, DAY, "RAW")


def test_no_network_without_live_and_explicit_issue(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    with pytest.raises(KisReadOnlyError, match="KIS_LIVE_READ_DISABLED"):
        fetch(cli(gate, stub, enabled=False, issue=True))
    assert stub.calls == []
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_TOKEN_MISSING_ISSUE_DENIED"):
        fetch(cli(gate, stub, issue=False))
    assert stub.calls == []
    assert not (directory / STATE_FILE).exists()


def test_first_issue_shared_reuse_after_restart_and_file_permissions(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    first = fetch(cli(gate, stub, issue=True))
    assert first.availability == "UNFINALIZED"
    assert first.bars[0].is_final is False
    clock.advance(1.3)
    restarted = cli(KisSharedState(directory, clock=clock), stub)
    second = fetch(restarted, US)
    assert second.availability == "UNFINALIZED"
    assert stub.calls == [
        ("POST", TOKEN_PATH), ("GET", KR_DAILY_PATH), ("GET", US_DAILY_PATH)
    ]
    assert (directory / STATE_FILE).stat().st_mode & 0o777 == 0o600
    assert (directory / LOCK_FILE).stat().st_mode & 0o777 == 0o600
    assert (directory / STATE_FILE).stat().st_uid == os.geteuid()
    content = json.loads((directory / STATE_FILE).read_text())
    assert content["token"] == "synthetic-token-123456"
    assert "synthetic-appsecret" not in str(content)
    assert len(content["requests"]) == 3


def test_quote_rate_limit_across_new_instances(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    fetch(cli(gate, stub, issue=True))
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_QUOTE_RATE_LIMIT"):
        fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == 2
    clock.advance(1.25)
    fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == 3


def test_token_expiry_blocks_second_issue_within_24h(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub(ttl=120)
    fetch(cli(gate, stub, issue=True))
    clock.advance(70)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_TOKEN_ISSUE_TOO_SOON"):
        fetch(cli(KisSharedState(directory, clock=clock), stub, issue=True))
    assert stub.calls == [("POST", TOKEN_PATH), ("GET", KR_DAILY_PATH)]


def test_token_attempt_is_durable_before_network_failure(tmp_path, capsys):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub(fail_token=True)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_TOKEN_REQUEST_FAILED"):
        fetch(cli(gate, stub, issue=True))
    assert len(stub.calls) == 1
    state_data = json.loads((directory / STATE_FILE).read_text())
    assert state_data["last_token_attempt"] == clock.value
    assert state_data["token"] is None
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_TOKEN_ISSUE_TOO_SOON"):
        fetch(cli(KisSharedState(directory, clock=clock), stub, issue=True))
    assert len(stub.calls) == 1
    assert "PRIVATE" not in capsys.readouterr().out


def test_failed_quote_debits_quota_and_cannot_retry_immediately(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub(fail_quote=True)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_QUOTE_REQUEST_FAILED"):
        fetch(cli(gate, stub, issue=True))
    assert len(stub.calls) == 2
    content = json.loads((directory / STATE_FILE).read_text())
    assert len(content["requests"]) == 2
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_QUOTE_RATE_LIMIT"):
        fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == 2


def test_shared_daily_cap_60_requests_over_rolling_day(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    fetch(cli(gate, stub, issue=True))
    for _ in range(MAX_HTTP_REQUESTS_24H - 2):
        clock.advance(1.25)
        fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == MAX_HTTP_REQUESTS_24H
    clock.advance(1.25)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_DAILY_CAP"):
        fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == MAX_HTTP_REQUESTS_24H


def test_clock_rollback_fails_closed(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    fetch(cli(gate, stub, issue=True))
    clock.advance(-10)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_CLOCK_ROLLBACK"):
        fetch(cli(KisSharedState(directory, clock=clock), stub))
    assert len(stub.calls) == 2


def test_lock_contention_does_not_request_or_wait(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    with gate._lock():
        with pytest.raises(KisSharedStateError, match="KIS_SHARED_LOCK_BUSY"):
            fetch(cli(KisSharedState(directory, clock=clock), stub, issue=True))
    assert stub.calls == []


def test_state_perms_and_symlink_rejected(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    fetch(cli(gate, stub, issue=True))
    file = directory / STATE_FILE
    file.chmod(0o644)
    clock.advance(2)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_STATE_UNSAFE"):
        fetch(cli(gate, stub))
    file.chmod(0o600)
    other = tmp_path / "other"
    file.rename(other)
    file.symlink_to(other)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_STATE_UNAVAILABLE"):
        fetch(cli(gate, stub))
    file.unlink()
    other.rename(file)
    directory.chmod(0o755)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_DIR_UNSAFE"):
        fetch(cli(gate, stub))


def test_corrupt_state_and_key_rotation_blocked_without_network(tmp_path):
    clock = Clock()
    gate, directory = state(tmp_path, clock)
    stub = Stub()
    fetch(cli(gate, stub, issue=True))
    before = len(stub.calls)
    bad_creds = KisCredentials("other-synthetic-appkey", "other-synthetic-appsecret")
    other_cli = KisReadOnlyDailyProvider(
        bad_creds, transport=stub, shared_state=gate,
        live_enabled=True, utcnow=lambda: NOW)
    clock.advance(2)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_CREDENTIAL_MISMATCH"):
        fetch(other_cli)
    assert len(stub.calls) == before
    (directory / STATE_FILE).write_text("{invalid-json")
    (directory / STATE_FILE).chmod(0o600)
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_STATE_INVALID"):
        fetch(cli(gate, stub))
    assert len(stub.calls) == before


def test_no_order_or_balance_path_and_no_implicit_shared_issuance(tmp_path):
    clock = Clock()
    gate, _ = state(tmp_path, clock)
    stub = Stub()
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_QUOTE_NOT_ALLOWED"):
        gate.call_quote(KEY, stub, path="/uapi/domestic-stock/v1/trading/order-cash",
                        tr_id="UNKNOWN", params={}, live_enabled=True,
                        allow_new_token=True)
    assert stub.calls == []
    with pytest.raises(KisReadOnlyError, match="KIS_SHARED_STATE_REQUIRED"):
        KisReadOnlyDailyProvider(KEY, allow_shared_token_issue=True)

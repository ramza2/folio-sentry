"""KIS one-shot preflight/probe tests; all quotes are synthetic and offline."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import kis_first_probe as probe
from app.kis_readonly import KisReadOnlyError


def private_args(tmp_path):
    key, secret = tmp_path / "appkey", tmp_path / "appsecret"
    key.write_text("synthetic-key\n")
    secret.write_text("synthetic-secret\n")
    key.chmod(0o600)
    secret.chmod(0o600)
    return ["--appkey-file", str(key), "--appsecret-file", str(secret)], key, secret


def test_check_is_metadata_only_no_secret_read_or_network(tmp_path, monkeypatch, capsys):
    flags, _, _ = private_args(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("check must not read secrets or open network")

    monkeypatch.setattr(probe.KisCredentials, "from_private_files", forbidden)
    monkeypatch.setattr(probe, "KisReadOnlyDailyProvider", forbidden)
    assert probe.run(["check", *flags]) == 0
    out = capsys.readouterr()
    assert "NO_SECRETS_READ_NO_NETWORK" in out.out
    assert "synthetic" not in str(out)


def test_reject_world_readable_symlink_missing_or_same_secret_file(tmp_path):
    flags, key, secret = private_args(tmp_path)
    key.chmod(0o644)
    assert probe.run(["check", *flags]) == 2
    key.chmod(0o600)
    key.unlink()
    key.symlink_to(secret)
    assert probe.run(["check", *flags]) == 2
    key.unlink()
    assert probe.run(["check", *flags]) == 2
    assert probe.run(["check", "--appkey-file", str(secret),
                      "--appsecret-file", str(secret)]) == 2


def test_live_requires_literal_confirmation_before_any_network_or_marker(
        tmp_path, monkeypatch):
    flags, _, _ = private_args(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert probe.run(["live", *flags, "--kr-date", "2026-11-19",
                      "--us-date", "2026-11-19"]) == 2
    assert not list(tmp_path.rglob(probe.MARKER))


@pytest.mark.parametrize("day", ["invalid", "2099-12-31", "2026-02-29", "20261119"])
def test_bad_live_date_never_creates_marker_or_network(tmp_path, monkeypatch, day):
    flags, _, _ = private_args(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert probe.run(["live", *flags, "--confirm", probe.CONFIRM,
                      "--kr-date", day, "--us-date", "2026-11-19"]) == 2
    assert not list(tmp_path.rglob(probe.MARKER))


def test_live_two_readonly_quotes_once_then_refuses_second_attempt(
        tmp_path, monkeypatch, capsys):
    flags, _, _ = private_args(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    invoked = []

    class StubProvider:
        def __init__(self, credentials, *, live_enabled):
            assert live_enabled is True
            invoked.append("constructor")

        def fetch_daily(self, identity, start, end, basis):
            invoked.append((identity.market, identity.symbol, start, end, basis))
            return SimpleNamespace(bars=(
                SimpleNamespace(is_final=False, source_observed_at=None),
            ))

    monkeypatch.setattr(probe, "KisReadOnlyDailyProvider", StubProvider)
    monkeypatch.setattr(probe.time, "sleep", lambda s: None)
    args = ["live", *flags, "--confirm", probe.CONFIRM,
            "--kr-date", "2026-11-19", "--us-date", "2026-11-19"]
    assert probe.run(args) == 0
    out = capsys.readouterr()
    assert "READONLY_QUOTE_SHAPE_PASS" in out.out
    assert "synthetic" not in str(out)
    assert invoked == [
        "constructor",
        ("KR", "005930", date(2026, 11, 19), date(2026, 11, 19), "RAW"),
        ("US", "AAPL", date(2026, 11, 19), date(2026, 11, 19), "RAW"),
    ]
    assert (tmp_path / ".local" / "state" / "folio-sentry" / probe.MARKER).exists()
    assert probe.run(args) == 2
    assert len(invoked) == 3


def test_quote_failure_not_retried_and_marker_is_preserved(tmp_path, monkeypatch):
    flags, _, _ = private_args(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = []

    class FailingProvider:
        def __init__(self, credentials, *, live_enabled):
            assert live_enabled

        def fetch_daily(self, identity, start, end, basis):
            calls.append(identity.market)
            raise KisReadOnlyError("KIS_NETWORK_UNAVAILABLE")

    monkeypatch.setattr(probe, "KisReadOnlyDailyProvider", FailingProvider)
    args = ["live", *flags, "--confirm", probe.CONFIRM,
            "--kr-date", "2026-11-19", "--us-date", "2026-11-19"]
    assert probe.run(args) == 2
    assert calls == ["KR"]
    assert (tmp_path / ".local" / "state" / "folio-sentry" / probe.MARKER).exists()


def test_empty_quote_not_mistaken_for_success(tmp_path, monkeypatch):
    flags, _, _ = private_args(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    class EmptyProvider:
        def __init__(self, credentials, *, live_enabled):
            assert live_enabled

        def fetch_daily(self, identity, start, end, basis):
            return SimpleNamespace(bars=())

    monkeypatch.setattr(probe, "KisReadOnlyDailyProvider", EmptyProvider)
    assert probe.run(["live", *flags, "--confirm", probe.CONFIRM,
                      "--kr-date", "2026-11-19",
                      "--us-date", "2026-11-19"]) == 3

"""Offline tests for MiniPC secure setup script. No real credentials or network."""
import importlib.util
from pathlib import Path
import sys

import pytest

MODULE = Path(__file__).resolve().parents[2] / "scripts" / "kis-secret-setup.py"
SPEC = importlib.util.spec_from_file_location("kis_secret_setup", MODULE)
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".config").mkdir()


def test_setup_then_check_no_plaintext_logs_or_argv(tmp_path, monkeypatch, capsys):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(subject.sys.stdin, "isatty", lambda: True)
    inputs = iter(["synthetic-app-key-123456789", "synthetic-app-secret-123456789"])
    monkeypatch.setattr(subject.getpass, "getpass", lambda prompt: next(inputs))
    assert subject.run(["setup"]) == 0
    paths = subject._paths()
    assert paths[0].read_text() == "synthetic-app-key-123456789"
    assert paths[1].read_text() == "synthetic-app-secret-123456789"
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths)
    assert paths[0].parent.stat().st_mode & 0o777 == 0o700
    assert subject.run(["check"]) == 0
    captured = capsys.readouterr()
    assert subject.SUCCESS in captured.out
    assert subject.CHECK_SUCCESS in captured.out
    assert "synthetic" not in captured.out + captured.err
    assert subject.run(["setup"]) == 2
    assert paths[0].read_text() == "synthetic-app-key-123456789"


def test_check_metadata_does_not_read_contents(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    private = tmp_path / ".config" / "folio-sentry"
    private.mkdir(mode=0o700)
    for name in subject.FILE_NAMES:
        path = private / name
        path.write_text("synthetic-fixture")
        path.chmod(0o600)
    monkeypatch.setattr(Path, "read_text",
                        lambda *args, **kw: pytest.fail("secret content read"))
    assert subject.run(["check"]) == 0


def test_refuses_insecure_dir_file_and_symlink(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    private = tmp_path / ".config" / "folio-sentry"
    private.mkdir(mode=0o755)
    assert subject.run(["check"]) == 2
    private.chmod(0o700)
    key = private / subject.FILE_NAMES[0]
    secret = private / subject.FILE_NAMES[1]
    key.write_text("synthetic")
    secret.write_text("synthetic")
    key.chmod(0o600)
    secret.chmod(0o644)
    assert subject.run(["check"]) == 2
    secret.chmod(0o600)
    assert subject.run(["check"]) == 0
    key.unlink()
    key.symlink_to(secret)
    assert subject.run(["check"]) == 2


def test_setup_refuses_noninteractive_without_reading_any_credentials(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(subject.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(subject.getpass, "getpass",
                        lambda prompt: pytest.fail("no prompt without a TTY"))
    assert subject.run(["setup"]) == 2
    assert not list(tmp_path.rglob("kis_appkey"))
    assert not list(tmp_path.rglob("kis_appsecret"))


@pytest.mark.parametrize("value", ["", " leading", "trailing ", "has space",
                                   "abc\nxyz", "a" * 257])
def test_reject_bad_secret_inputs_with_no_files(tmp_path, monkeypatch, value):
    _home(tmp_path, monkeypatch)
    monkeypatch.setattr(subject.sys.stdin, "isatty", lambda: True)
    values = iter([value, "synthetic-secret"])
    monkeypatch.setattr(subject.getpass, "getpass", lambda prompt: next(values))
    assert subject.run(["setup"]) == 2
    assert not list(tmp_path.rglob("kis_appkey"))
    assert not list(tmp_path.rglob("kis_appsecret"))

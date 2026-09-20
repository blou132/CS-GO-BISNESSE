import os

import pytest
from nacl.signing import SigningKey

from app.core import market_credentials as credentials


def target(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    return directory / "markets.env"


def test_atomic_credential_update_preserves_unrelated_dotenv_and_backup(tmp_path):
    path = target(tmp_path)
    original = "# keep\nexport OTHER='multi\nline $NOT_EXPANDED'\nCSFLOAT_API_KEY=''\n"
    path.write_text(original)
    path.chmod(0o600)
    assert credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_123456789"})
    assert "export OTHER='multi\nline $NOT_EXPANDED'" in path.read_text()
    assert credentials.load(path)["csfloat_api_key"] == "TEST_ONLY_123456789"
    backup = next(path.parent.glob("markets.env.backup-*"))
    assert backup.read_text() == original
    assert backup.stat().st_mode & 0o777 == path.stat().st_mode & 0o777 == 0o600
    assert path.stat().st_uid == os.getuid()
    assert not list(path.parent.glob(".markets-*"))


def test_credential_backups_are_bounded_and_noop_does_not_rewrite(tmp_path):
    path = target(tmp_path)
    for i in range(6):
        credentials.save(path, {"CSFLOAT_API_KEY": f"TEST_ONLY_123456789_{i}"})
    assert len(list(path.parent.glob("markets.env.backup-*"))) == 3
    before = path.stat().st_mtime_ns
    assert not credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_123456789_5"})
    assert path.stat().st_mtime_ns == before


@pytest.mark.parametrize(
    "value",
    [
        "short",
        "TEST key with spaces",
        "TEST_ONLY\nINJECT=1",
        "github_pat_" + "A" * 60,
        "TEST_ONLY_${SECRET}",
    ],
)
def test_bad_credentials_are_not_written_or_disclosed(tmp_path, value):
    path = target(tmp_path)
    with pytest.raises(ValueError) as error:
        credentials.save(path, {"CSFLOAT_API_KEY": value})
    assert value not in str(error.value)
    assert not path.exists()


def test_dmarket_pair_validation_accepts_seed_and_rejects_mismatch(tmp_path):
    key = SigningKey.generate()
    public = bytes(key.verify_key).hex()
    private = bytes(key).hex()
    for secret in (private, private + public):
        credentials.validate({"DMARKET_PUBLIC_KEY": public, "DMARKET_SECRET_KEY": secret})
    for changes in (
        {"DMARKET_PUBLIC_KEY": public},
        {"DMARKET_PUBLIC_KEY": "0" * 64, "DMARKET_SECRET_KEY": private},
        {"DMARKET_PUBLIC_KEY": public, "DMARKET_SECRET_KEY": private + "0" * 64},
    ):
        with pytest.raises(ValueError):
            credentials.save(tmp_path / "new/markets.env", changes)


def test_credential_file_links_permissions_and_git_are_refused(tmp_path):
    path = target(tmp_path)
    path.write_text("CSFLOAT_API_KEY='TEST_ONLY_123456789'\n")
    with pytest.raises(ValueError):
        credentials.load(path)
    path.chmod(0o600)
    link = path.parent / "linked.env"
    link.symlink_to(path)
    with pytest.raises(OSError):
        credentials.load(link)
    link.unlink()
    os.link(path, link)
    with pytest.raises(ValueError):
        credentials.load(path)
    link.unlink()
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError):
        credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_987654321"})


def test_duplicate_or_malformed_dotenv_is_not_silently_replaced(tmp_path):
    path = target(tmp_path)
    for content in ("CSFLOAT_API_KEY=a\nCSFLOAT_API_KEY=b\n", "OTHER='unterminated\n"):
        path.write_text(content)
        path.chmod(0o600)
        with pytest.raises(ValueError):
            credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_123456789"})
        assert path.read_text() == content


def test_interrupted_atomic_replace_keeps_original_and_secure_backup(tmp_path, monkeypatch):
    path = target(tmp_path)
    credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_123456789"})
    original = path.read_text()
    replace = credentials.os.replace

    def fail_current(source, destination):
        if destination == path:
            raise OSError("TEST_PRIVATE_ERROR")
        return replace(source, destination)

    monkeypatch.setattr(credentials.os, "replace", fail_current)
    with pytest.raises(OSError):
        credentials.save(path, {"CSFLOAT_API_KEY": "TEST_ONLY_987654321"})
    assert path.read_text() == original
    assert len(list(path.parent.glob("markets.env.backup-*"))) == 1
    assert not list(path.parent.glob(".markets-*"))


def test_status_prints_booleans_only_and_interactive_input_is_hidden(tmp_path, monkeypatch, capsys):
    path = target(tmp_path)
    monkeypatch.setattr(credentials, "default_path", lambda: path)
    monkeypatch.setattr("sys.argv", ["credentials"])
    monkeypatch.setattr(credentials.sys.stdin, "isatty", lambda: True)
    supplied = iter(["TEST_ONLY_123456789", "", ""])
    monkeypatch.setattr(credentials.getpass, "getpass", lambda prompt: next(supplied))
    assert credentials.main() == 0
    monkeypatch.setattr("sys.argv", ["credentials", "--status"])
    assert credentials.main() == 0
    output = capsys.readouterr()
    assert "CONFIGURED" in output.out
    assert "TEST_ONLY_123456789" not in output.out + output.err


def test_noninteractive_entry_refuses_input(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["credentials"])
    monkeypatch.setattr(credentials, "default_path", lambda: target(tmp_path))
    monkeypatch.setattr(credentials.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(credentials.getpass, "getpass", lambda prompt: pytest.fail("No input"))
    assert credentials.main() == 2
    assert "refused" in capsys.readouterr().err

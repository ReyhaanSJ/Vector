import io
import json
import time
import zipfile

import pytest

from vector import __version__, updater
from vector.updater import Release, UpdateError, is_newer, parse_version


def test_versions_match_everywhere():
    import tomllib
    from pathlib import Path

    meta = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert meta["project"]["version"] == __version__


def test_parse_and_compare():
    assert parse_version("v0.10.2") == (0, 10, 2)
    assert parse_version("1.2-beta") == (1, 2)
    assert is_newer("v0.10.0", "0.9.9")
    assert is_newer("1.0", "0.9")
    assert not is_newer("0.2", "0.2.0")
    assert not is_newer("v0.1.9", "0.2.0")
    with pytest.raises(UpdateError):
        parse_version("latest")


def _releases(*tags):
    return [Release(tag=t, name=t, notes=f"Notes for {t}", published="2026-11-01") for t in tags]


def test_check_for_update_caches_daily(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "CHECK_FILE", tmp_path / "check.json")
    calls = []

    def fake_list(include_prereleases=False):
        calls.append(1)
        return _releases("v99.0.0", "v0.1.0")

    monkeypatch.setattr(updater, "list_releases", fake_list)
    assert updater.check_for_update().tag == "v99.0.0"
    assert updater.check_for_update().tag == "v99.0.0"   # from the cache
    assert len(calls) == 1
    data = json.loads((tmp_path / "check.json").read_text())
    data["checked"] = time.time() - 2 * 24 * 3600         # a day later: asks GitHub again
    (tmp_path / "check.json").write_text(json.dumps(data))
    updater.check_for_update()
    assert len(calls) == 2


def test_no_update_when_current(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "CHECK_FILE", tmp_path / "check.json")
    monkeypatch.setattr(updater, "list_releases", lambda include_prereleases=False: _releases(f"v{__version__}"))
    assert updater.check_for_update(force=True) is None


def test_find_release(monkeypatch):
    monkeypatch.setattr(updater, "list_releases",
                        lambda include_prereleases=False: _releases("v0.3.0", "v0.2.0"))
    assert updater.find_release("0.2.0").tag == "v0.2.0"
    assert updater.find_release("v0.3").tag == "v0.3.0"
    with pytest.raises(UpdateError):
        updater.find_release("5.0")


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def test_download_release_finds_installer(tmp_path, monkeypatch):
    data = _zip({f"ReyhaanSJ-Vector-abc123/{updater.INSTALLER}": "# installer",
                 "ReyhaanSJ-Vector-abc123/vector/__init__.py": ""})
    monkeypatch.setattr(updater, "_request", lambda url, accept=None: _FakeResponse(data))
    folder = updater.download_release(_releases("v0.2.0")[0], tmp_path)
    assert (folder / updater.INSTALLER).read_text() == "# installer"


def test_download_release_rejects_unsafe_zip(tmp_path, monkeypatch):
    data = _zip({"../evil.txt": "x", f"a/{updater.INSTALLER}": ""})
    monkeypatch.setattr(updater, "_request", lambda url, accept=None: _FakeResponse(data))
    with pytest.raises(UpdateError):
        updater.download_release(_releases("v0.2.0")[0], tmp_path / "dl")


def test_download_asks_github_for_the_normal_format(tmp_path, monkeypatch):
    """Regression: asking the zipball endpoint for octet-stream made GitHub answer 415."""
    seen = {}

    def fake_request(url, accept="application/vnd.github+json"):
        seen["accept"] = accept
        return _FakeResponse(_zip({f"x/{updater.INSTALLER}": ""}))

    monkeypatch.setattr(updater, "_request", fake_request)
    updater.download_release(_releases("v0.2.3")[0], tmp_path)
    assert seen["accept"] == "application/vnd.github+json"


def test_mac_and_windows_installers_are_found_by_name(tmp_path, monkeypatch):
    data = _zip({"v/install.sh": "#!/bin/bash", "v/install.ps1": "# ps"})
    monkeypatch.setattr(updater, "_request", lambda url, accept=None: _FakeResponse(data))
    for name in ("install.sh", "install.ps1"):
        monkeypatch.setattr(updater, "INSTALLER", name)
        folder = updater.download_release(_releases("v0.4.1")[0], tmp_path / name)
        assert (folder / name).exists()


@pytest.mark.skipif(not __import__("os").environ.get("VECTOR_LIVE_UPDATE_TEST"),
                    reason="needs network + GitHub access (CI sets VECTOR_LIVE_UPDATE_TEST)")
def test_real_release_downloads(tmp_path):
    latest = updater.latest_release()
    assert latest is not None
    folder = updater.download_release(latest, tmp_path)
    assert (folder / "install.ps1").exists() and (folder / "Install VECTOR.bat").exists()

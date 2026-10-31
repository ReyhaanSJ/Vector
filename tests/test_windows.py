"""Windows support. The first group runs everywhere; the rest only on Windows (CI has a runner)."""

import sys

import pytest

from vector import startup
from vector.skills.apps import best_app_match
from vector.skills.windows import settings_uri

APPS = [
    ("Visual Studio Code", "Microsoft.VisualStudioCode"),
    ("Spotify", "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"),
    ("Microsoft Edge", "MSEdge"),
    ("Microsoft Edge Dev", "MSEdgeDev"),
    ("Calculator", "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"),
    ("Word", "Microsoft.Office.WINWORD.EXE.15"),
]


def test_best_app_match():
    assert best_app_match("spotify", APPS)[0] == "Spotify"
    assert best_app_match("Visual Studio Code", APPS)[0] == "Visual Studio Code"
    assert best_app_match("edge", APPS)[0] == "Microsoft Edge"  # shortest wins over "Edge Dev"
    assert best_app_match("calc", APPS)[0] == "Calculator"
    assert best_app_match("studio", APPS)[0] == "Visual Studio Code"
    assert best_app_match("photoshop", APPS) is None
    assert best_app_match("", APPS) is None


def test_settings_uri():
    assert settings_uri("Wi-Fi") == "ms-settings:network-wifi"
    assert settings_uri("bluetooth") == "ms-settings:bluetooth"
    assert settings_uri("update") == "ms-settings:windowsupdate"
    assert settings_uri("nonsense page") is None


def test_startup_enable_disable(tmp_path):
    path = startup.enable(voice=True, folder=tmp_path)
    text = path.read_text()
    assert "-m vector --voice" in text and sys.executable in text
    assert startup.disable(folder=tmp_path) is True
    assert startup.disable(folder=tmp_path) is False


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


@windows_only
def test_windows_skills_registered():
    from vector.registry import REGISTRY, load_builtin_skills

    load_builtin_skills()
    for name in ("open_windows_settings", "set_dark_mode", "set_brightness", "wifi_status"):
        assert name in REGISTRY
    assert REGISTRY.get("empty_recycle_bin").dangerous


@windows_only
def test_os_name_reports_windows_version():
    from vector.agent import _os_name

    assert _os_name().startswith("Windows ")


@windows_only
def test_personal_folders_come_from_registry():
    from vector.osutil import personal_folders

    folders = personal_folders()
    assert folders["downloads"].is_absolute() and "%" not in str(folders["downloads"])
    assert folders["documents"].exists()


@windows_only
def test_shell_commands_run_in_powershell():
    from vector.skills.system import run_shell_command

    out = run_shell_command("$PSVersionTable.PSVersion.Major; Write-Output 'héllo'")
    assert out.startswith("exit code 0")
    assert "héllo" in out


@windows_only
def test_start_menu_lookup():
    from vector.skills.apps import windows_start_apps

    apps = windows_start_apps()
    assert isinstance(apps, tuple)
    print(f"{len(apps)} Start-menu apps, e.g. {apps[:3]}")


@windows_only
def test_dark_mode_roundtrip():
    import winreg

    from vector.skills.windows import set_dark_mode

    path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            original = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
    except OSError:
        original = 1
    try:
        set_dark_mode(True)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            assert winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    finally:
        set_dark_mode(original == 0)


@windows_only
def test_helpers_do_not_crash():
    from vector.osutil import notify
    from vector.skills.system import system_status
    from vector.skills.windows import wifi_status

    notify("VECTOR test", "hello from CI")
    assert isinstance(wifi_status(), str)
    assert "CPU" in system_status()

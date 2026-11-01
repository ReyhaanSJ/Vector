"""App pieces that don't need a screen, microphone or speakers."""

import numpy as np
import pytest

from vector.app import describe_step
from vector.hotkey import HotkeyError, parse_hotkey, to_pynput
from vector.instance import InstanceServer, signal_running
from vector.voice import BLOCK, Segmenter, loudness


def test_parse_hotkey():
    assert parse_hotkey("ctrl+shift+space") == (0x2 | 0x4, 0x20)
    assert parse_hotkey("Ctrl + Alt + V") == (0x2 | 0x1, ord("V"))
    assert parse_hotkey("win+f9") == (0x8, 0x78)
    for bad in ("space", "ctrl+banana", "hyper+v", ""):
        with pytest.raises(HotkeyError):
            parse_hotkey(bad)
    assert to_pynput("ctrl+shift+space") == "<ctrl>+<shift>+<space>"
    assert to_pynput("ctrl+alt+v") == "<ctrl>+<alt>+v"


def _blocks(level: int, seconds: float):
    rng = np.random.default_rng(0)
    for _ in range(int(seconds * 10)):
        yield (rng.standard_normal(BLOCK) * level).astype(np.int16)


def test_segmenter_cuts_one_phrase():
    seg = Segmenter(noise_floor=100)
    states = [seg.feed(b) for b in _blocks(30, 1.0)]      # quiet room
    assert set(states) == {"waiting"}
    states = [seg.feed(b) for b in _blocks(3000, 1.5)]    # someone speaks
    assert states[0] == "speaking"
    result = None
    for b in _blocks(30, 2.0):                            # then stops
        result = seg.feed(b)
        if result == "done":
            break
    assert result == "done"
    # pre-roll (0.3 s) + speech (1.5 s) + trailing silence (~0.9 s)
    assert 2.4 <= seg.duration <= 2.9
    assert loudness(seg.audio) > 500


def test_segmenter_times_out_when_nobody_speaks():
    seg = Segmenter(noise_floor=100, start_timeout=1.0)
    assert [seg.feed(b) for b in _blocks(30, 1.0)][-1] == "timeout"


def test_segmenter_stops_at_max_length():
    seg = Segmenter(noise_floor=100, max_seconds=2.0)
    states = []
    for block in _blocks(3000, 3.0):
        states.append(seg.feed(block))
        if states[-1] == "done":
            break
    assert len(states) < 30 and round(seg.duration, 1) == 2.0


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_single_instance_messages():
    got = []
    port = _free_port()
    server = InstanceServer(got.append, port=port)
    assert server.start()
    try:
        assert not InstanceServer(got.append, port=port).start()  # second app can't take over
        assert signal_running("show", port=port)
        assert signal_running("nonsense", port=port)
        import time

        time.sleep(0.2)
        assert got == ["show"]
    finally:
        server.stop()
    assert not signal_running("show", port=port)


def test_describe_step():
    assert describe_step("open_app", {"name": "spotify"}) == "Open app: spotify"
    assert describe_step("show_desktop", {}) == "Show desktop"
    assert describe_step("write_text_file", {"path": "x" * 80, "content": "hi"}).endswith("...")


def test_speech_models_present(tmp_path, monkeypatch):
    from vector.voice import speech_models_present

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    assert not speech_models_present("base.en")
    (tmp_path / ".cache/vosk/vosk-model-small-en-us-0.15").mkdir(parents=True)
    assert not speech_models_present("base.en")
    snap = tmp_path / ".cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots/abc"
    snap.mkdir(parents=True)
    (snap / "model.bin").write_bytes(b"x")
    assert speech_models_present("base.en")
    assert not speech_models_present("small.en")

"""End-to-end speech test: Windows' own voice speaks a command into a WAV file, which is
played through VECTOR's real listening pipeline (wake word -> record -> Whisper) via a fake
microphone. Opt-in because it downloads ~200 MB of models:
    VECTOR_SPEECH_E2E=1 pytest tests/test_speech_e2e.py
"""

import os
import sys
import threading
import wave

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("VECTOR_SPEECH_E2E") != "1" or sys.platform != "win32",
    reason="opt-in speech test (Windows)")


def synthesize(text: str, path) -> None:
    from vector.osutil import powershell, ps_quote

    result = powershell(
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, "
        "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
        "[System.Speech.AudioFormat.AudioChannel]::Mono);"
        f"$s.SetOutputToWaveFile({ps_quote(str(path))}, $f); $s.Speak({ps_quote(text)}); $s.Dispose()",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


class WavMicrophone:
    """Plays audio into the engine as if it came from a microphone, then goes silent."""

    def __init__(self, audio, stop: threading.Event):
        from vector.voice import BLOCK

        self.blocks = [audio[i:i + BLOCK] for i in range(0, len(audio) - BLOCK + 1, BLOCK)]
        self.silence = audio[:BLOCK] * 0
        self._done = stop
        self.extra = 0
        self.muted = False

    def read(self, timeout=0.5):
        if self.blocks:
            return self.blocks.pop(0)
        self.extra += 1
        if self.extra > 100:      # 10 s of silence after the clip: give up
            self._done.set()
        return self.silence

    def start(self):
        pass

    def stop(self):
        pass

    def drain(self):
        pass


def _speech(tmp_path, text):
    import numpy as np

    wav = tmp_path / "clip.wav"
    synthesize(text, wav)
    with wave.open(str(wav)) as w:
        speech = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    quiet = np.zeros(16000, dtype=np.int16)
    return np.concatenate([quiet, speech, quiet, quiet])


@pytest.mark.parametrize("spoken, expected", [
    ("Vector. Open notepad.", "notepad"),          # pause after the wake word
    ("Vector, what time is it", "time"),           # all in one breath
])
def test_engine_hears_wake_word_and_command(tmp_path, spoken, expected):
    from vector.voice import VoiceEngine

    stop = threading.Event()
    mic = WavMicrophone(_speech(tmp_path, spoken), stop)
    engine = VoiceEngine("vector", "base.en", speak=False, mic=mic)
    engine.start()
    woke = []
    command = engine.listen_for_command(stop=stop, on_wake=lambda: woke.append(True))
    assert woke, "wake word not detected"
    assert command is not None and expected in command.lower(), repr(command)


def test_no_wake_word_means_no_command(tmp_path):
    from vector.voice import VoiceEngine

    stop = threading.Event()
    mic = WavMicrophone(_speech(tmp_path, "Open notepad please."), stop)
    engine = VoiceEngine("vector", "base.en", speak=False, mic=mic)
    engine.start()
    assert engine.listen_for_command(stop=stop) is None

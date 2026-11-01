"""End-to-end speech test: Windows' own voice says a command into a WAV file, and VECTOR's
wake-word spotter and Whisper transcriber must understand it. Opt-in (downloads ~200 MB):
    VECTOR_SPEECH_E2E=1 pytest tests/test_speech_e2e.py
"""

import os
import sys
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


def test_wake_word_then_command(tmp_path):
    import numpy as np

    from vector.voice import (
        BLOCK,
        WAKE_VARIANTS,
        KeywordSpotter,
        Segmenter,
        Transcriber,
        strip_wake_word,
    )

    wav = tmp_path / "cmd.wav"
    synthesize("Vector. Open notepad.", wav)
    with wave.open(str(wav)) as w:
        speech = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    silence = np.zeros(16000, dtype=np.int16)
    audio = np.concatenate([silence, speech, silence, silence])
    blocks = [audio[i:i + BLOCK] for i in range(0, len(audio) - BLOCK + 1, BLOCK)]

    spotter = KeywordSpotter(["vector", *WAKE_VARIANTS])
    woke_at = next((i for i, b in enumerate(blocks) if spotter.feed(b)), None)
    assert woke_at is not None, "wake word not detected"

    seg = Segmenter(noise_floor=50, already_speaking=True)
    for b in blocks[woke_at:]:
        if seg.feed(b) == "done":
            break
    text = Transcriber("base.en").transcribe(seg.audio)
    command = strip_wake_word(text, "vector")
    command = (command if command is not None else text).lower()
    assert "notepad" in command, text

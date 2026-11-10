"""Hands-free voice: say "Vector, ..." and VECTOR hears you. No button to press.

How it works, all on this computer (nothing is sent anywhere while it waits):
  1. Wake word - a small offline speech model (Vosk) listens only for "Vector".
  2. Your command - recorded until you stop talking, then turned into text by
     Whisper (faster-whisper), also offline.
  3. Replies are spoken with Windows' built-in voice (pyttsx3 on macOS/Linux).

Install with:  pip install "vector-assistant[voice]"
The speech models (~200 MB) download automatically the first time.
"""

from __future__ import annotations

import collections
import json
import queue
import threading
import time

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1
BLOCK = int(SAMPLE_RATE * BLOCK_SECONDS)

# Things speech recognisers commonly hear instead of "vector".
WAKE_VARIANTS = ("vector", "victor", "vektor")
YES_WORDS = {"yes", "yeah", "yep", "sure", "allow", "okay", "ok", "confirm", "go"}
NO_WORDS = {"no", "nope", "deny", "cancel", "stop", "don't"}
WHISPER_HINT = "Vector, open Spotify and set the volume to 30."


NO_PORTAUDIO = ("Voice can't reach this computer's sound system (PortAudio is missing). On Linux: "
                "sudo apt install libportaudio2, then reopen VECTOR. Typing works fine meanwhile.")


class VoiceUnavailable(RuntimeError):
    """Voice can't run here; the message says why and what to do."""


def strip_wake_word(heard: str, wake_word: str) -> str | None:
    """Return the command after the wake word, "" if only the wake word, None if absent."""
    lowered = heard.lower()
    wake = wake_word.lower()
    variants = {wake, *WAKE_VARIANTS, "hey " + wake, "ok " + wake, "okay " + wake}
    for v in sorted(variants, key=len, reverse=True):
        idx = lowered.find(v)
        if idx != -1:
            return heard[idx + len(v):].lstrip(" ,.!?")
    return None


def _np():
    try:
        import numpy as np
    except ImportError as exc:
        raise VoiceUnavailable('Voice needs extra packages: pip install "vector-assistant[voice]"') from exc
    return np


def loudness(block) -> float:
    """Root-mean-square level of a block of 16-bit samples."""
    np = _np()
    if len(block) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block.astype(np.float32)))))


class Segmenter:
    """Cuts one spoken phrase out of a stream of 0.1 s blocks, using loudness.

    feed() returns "waiting" (no speech yet), "speaking", "done" (phrase ended)
    or "timeout" (nobody spoke).
    """

    def __init__(self, noise_floor: float = 200.0, start_timeout: float = 5.0,
                 end_silence: float = 0.9, max_seconds: float = 12.0, pre_roll: int = 3,
                 already_speaking: bool = False):
        self.threshold = max(noise_floor * 3.0, 450.0)
        # Count whole blocks (adding up 0.1 s floats never quite reaches the limit).
        self.start_blocks = round(start_timeout / BLOCK_SECONDS)
        self.silence_blocks = round(end_silence / BLOCK_SECONDS)
        self.max_blocks = round(max_seconds / BLOCK_SECONDS)
        self._pre = collections.deque(maxlen=pre_roll)
        self._blocks: list = []
        self._waited = 0
        self._silence = 0
        self.started = already_speaking

    def feed(self, block) -> str:
        level = loudness(block)
        if not self.started:
            self._pre.append(block)
            self._waited += 1
            if level >= self.threshold:
                self.started = True
                self._blocks.extend(self._pre)
                return "speaking"
            return "timeout" if self._waited >= self.start_blocks else "waiting"
        self._blocks.append(block)
        self._silence = self._silence + 1 if level < self.threshold else 0
        if self._silence >= self.silence_blocks or len(self._blocks) >= self.max_blocks:
            return "done"
        return "speaking"

    @property
    def duration(self) -> float:
        return len(self._blocks) * BLOCK_SECONDS

    @property
    def audio(self):
        np = _np()
        if not self._blocks:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(self._blocks)


class Microphone:
    """Streams 0.1 s blocks of 16 kHz mono audio from the default microphone."""

    def __init__(self):
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise VoiceUnavailable(
                'Voice needs extra packages: pip install "vector-assistant[voice]"') from exc
        except OSError as exc:  # the package is there, but the sound system it uses isn't
            raise VoiceUnavailable(NO_PORTAUDIO) from exc
        self._sd = sd
        self._queue: queue.Queue = queue.Queue(maxsize=300)
        self._stream = None
        self.muted = False

    def _callback(self, indata, frames, time_info, status):  # runs on the audio thread
        if self.muted:
            return
        try:
            self._queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def start(self) -> None:
        if self._stream is not None:
            return
        try:
            self._sd.check_input_settings(samplerate=SAMPLE_RATE, channels=1, dtype="int16")
            self._stream = self._sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                                blocksize=BLOCK, callback=self._callback)
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise VoiceUnavailable(
                "No working microphone found. Plug one in, or allow microphone access in "
                "Settings > Privacy & security > Microphone (\"Let desktop apps access your "
                f"microphone\"). Details: {exc}") from exc

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: float = 0.5):
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


_vosk_model = None
_vosk_lock = threading.Lock()


def vosk_model():
    """The small offline English model (~40 MB, downloaded once to ~/.cache/vosk)."""
    global _vosk_model
    with _vosk_lock:
        if _vosk_model is None:
            try:
                import vosk
            except ImportError as exc:
                raise VoiceUnavailable(
                    'Voice needs extra packages: pip install "vector-assistant[voice]"') from exc
            vosk.SetLogLevel(-1)
            try:
                _vosk_model = vosk.Model(lang="en-us")
            except Exception as exc:
                raise VoiceUnavailable(
                    f"Couldn't load the wake-word model (needs internet the first time): {exc}") from exc
        return _vosk_model


class KeywordSpotter:
    """Listens for a few specific words only, which makes it fast, light and accurate."""

    def __init__(self, words: list[str]):
        import vosk

        self.words = [w.lower() for w in words]
        grammar = json.dumps(sorted(set(self.words)) + ["[unk]"])
        self._rec = vosk.KaldiRecognizer(vosk_model(), SAMPLE_RATE, grammar)

    def feed(self, block) -> str | None:
        """Returns the first listed word heard in this block, if any."""
        if self._rec.AcceptWaveform(block.tobytes()):
            text = json.loads(self._rec.Result()).get("text", "")
        else:
            text = json.loads(self._rec.PartialResult()).get("partial", "")
        for word in text.split():
            if word in self.words:
                self._rec.Reset()
                return word
        return None

    def reset(self) -> None:
        self._rec.Reset()


def speech_models_present(whisper_model: str = "base.en") -> bool:
    """True if both speech models are already downloaded (so nothing needs fetching)."""
    import os
    from pathlib import Path

    vosk_dir = Path.home() / ".cache" / "vosk"
    has_vosk = any(vosk_dir.glob("vosk-model-small-en-us-*")) if vosk_dir.exists() else False
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    hub = Path(os.environ.get("HF_HUB_CACHE", hf_home / "hub"))
    has_whisper = any(hub.glob(f"models--*--faster-whisper-{whisper_model}/snapshots/*/model.bin"))
    return has_vosk and has_whisper


class Transcriber:
    """Offline speech-to-text with Whisper. The model downloads once (~150 MB for base.en)."""

    def __init__(self, model_name: str = "base.en"):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise VoiceUnavailable(
                        'Voice needs extra packages: pip install "vector-assistant[voice]"') from exc
                try:
                    self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
                except Exception as exc:
                    raise VoiceUnavailable(
                        f"Couldn't load the speech model '{self.model_name}' "
                        f"(needs internet the first time): {exc}") from exc
        return self._model

    def transcribe(self, audio) -> str:
        np = _np()
        if len(audio) < SAMPLE_RATE * 0.3:
            return ""
        samples = audio.astype(np.float32) / 32768.0
        segments, _ = self.load().transcribe(
            samples, language="en", beam_size=1, initial_prompt=WHISPER_HINT,
            condition_on_previous_text=False, vad_filter=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()


class Speaker:
    """Speaks text out loud: Windows' or macOS' own voice, pyttsx3 on Linux."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._engine = None
        self._proc = None
        self._stopped = threading.Event()

    def stop(self) -> None:
        """Stop talking right now (Esc)."""
        self._stopped.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def _run(self, cmd: list[str], stdin_text: str | None = None) -> None:
        """Speak with a helper program that Esc can stop (kill) at any moment."""
        import subprocess
        import sys

        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        except OSError:
            self.enabled = False  # no speech program here; stay silent
            return
        try:
            if stdin_text is not None:
                try:
                    self._proc.stdin.write(stdin_text.encode("utf-8"))
                    self._proc.stdin.close()
                except OSError:
                    pass  # stopped (killed) before it finished reading
            self._proc.wait(timeout=120)
        except BaseException:  # timeout, or Ctrl+C in the terminal: don't keep talking
            self._proc.kill()
            if not isinstance(sys.exc_info()[1], subprocess.TimeoutExpired):
                raise
        finally:
            self._proc = None

    def say(self, text: str) -> None:
        if not self.enabled or not text.strip():
            return
        import sys

        self._stopped.clear()
        if sys.platform == "win32":
            from vector.osutil import ps_quote

            script = ("Add-Type -AssemblyName System.Speech;"
                      "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                      f"$s.Rate = 1; $s.Speak({ps_quote(text[:1500])})")
            self._run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])
            return
        if sys.platform == "darwin":
            # macOS' own voice. Text goes in on stdin, so nothing in it is read as an option.
            self._run(["say", "-r", "190"], stdin_text=text[:1500])
            return
        try:
            if self._engine is None:
                import pyttsx3

                self._engine = pyttsx3.init()
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            self.enabled = False  # no speech engine here; stay silent


class VoiceEngine:
    """Wake word -> record -> transcribe, plus speaking. Use as a context manager."""

    def __init__(self, wake_word: str = "vector", whisper_model: str = "base.en", speak: bool = True,
                 mic=None):
        self.wake_word = wake_word.lower()
        self.mic = mic if mic is not None else Microphone()
        self.transcriber = Transcriber(whisper_model)
        self.speaker = Speaker(speak)
        self.noise_floor = 200.0
        self._wake = None

    # -- setup ---------------------------------------------------------------------------
    @staticmethod
    def prepare(whisper_model: str = "base.en") -> None:
        """Download the speech models now so the first "Vector" is instant."""
        vosk_model()
        Transcriber(whisper_model).load()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self) -> None:
        self._wake = KeywordSpotter([self.wake_word, *WAKE_VARIANTS])
        self.transcriber.load()
        self.mic.start()

    def stop(self) -> None:
        self.mic.stop()

    # -- listening -----------------------------------------------------------------------
    def _track_noise(self, block) -> None:
        level = loudness(block)
        if level < self.noise_floor * 4:
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * max(level, 50.0)

    def wait_for_wake_word(self, stop: threading.Event | None = None) -> bool:
        """Blocks until "Vector" is heard (True) or stop is set (False)."""
        self._wake.reset()
        while not (stop and stop.is_set()):
            block = self.mic.read()
            if block is None:
                continue
            self._track_noise(block)
            if self._wake.feed(block):
                return True
        return False

    def record_phrase(self, start_timeout: float = 5.0, already_speaking: bool = False):
        seg = Segmenter(self.noise_floor, start_timeout=start_timeout,
                        already_speaking=already_speaking)
        while True:
            block = self.mic.read(timeout=1.0)
            if block is None:
                continue
            state = seg.feed(block)
            if state in ("done", "timeout"):
                return seg.audio if state == "done" else None

    def listen_for_command(self, stop: threading.Event | None = None, on_wake=None) -> str | None:
        """Wait for "Vector", then return what was said after it.
        None if stopped; "" if only the wake word was heard."""
        if not self.wait_for_wake_word(stop):
            return None
        if on_wake:
            on_wake()
        audio = self.record_phrase(start_timeout=4.0)
        if audio is None:
            return ""
        text = self.transcriber.transcribe(audio)
        stripped = strip_wake_word(text, self.wake_word)
        return (stripped if stripped is not None else text).strip(" .")

    def listen_once(self, start_timeout: float = 6.0) -> str:
        """Record and transcribe one phrase without waiting for the wake word."""
        audio = self.record_phrase(start_timeout=start_timeout)
        return "" if audio is None else self.transcriber.transcribe(audio).strip(" .")

    def ask_yes_no(self, timeout: float = 8.0, cancel: threading.Event | None = None) -> bool | None:
        """Listen for yes/no. None if no clear answer before the timeout."""
        spotter = KeywordSpotter(sorted(YES_WORDS | NO_WORDS))
        self.mic.drain()
        end = time.monotonic() + timeout
        while time.monotonic() < end and not (cancel and cancel.is_set()):
            block = self.mic.read(timeout=0.5)
            if block is None:
                continue
            word = spotter.feed(block)
            if word in YES_WORDS:
                return True
            if word in NO_WORDS:
                return False
        return None

    # -- speaking ------------------------------------------------------------------------
    def stop_speaking(self) -> None:
        self.speaker.stop()

    def say(self, text: str) -> None:
        """Speak with the mic muted, so VECTOR doesn't hear itself."""
        self.mic.muted = True
        try:
            self.speaker.say(text)
        finally:
            time.sleep(0.2)
            self.mic.drain()
            self.mic.muted = False

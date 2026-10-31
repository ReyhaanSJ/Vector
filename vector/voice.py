"""Optional voice I/O: speech recognition + text-to-speech.

Install with:  pip install "vector-assistant[voice]"
(On Linux you may also need: sudo apt install portaudio19-dev espeak-ng)
"""

from __future__ import annotations


class VoiceUnavailable(RuntimeError):
    pass


class Voice:
    def __init__(self, speak_replies: bool = True):
        try:
            import speech_recognition as sr
        except ImportError as exc:
            raise VoiceUnavailable(
                'Voice mode needs extra packages: pip install "vector-assistant[voice]"'
            ) from exc
        self.sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        try:
            self.mic = sr.Microphone()
        except (OSError, AttributeError) as exc:
            raise VoiceUnavailable(f"No microphone available ({exc}). Is PyAudio installed?") from exc
        self.engine = None
        if speak_replies:
            try:
                import pyttsx3

                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 185)
            except Exception:
                self.engine = None  # still usable, just silent
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.8)

    def listen(self, timeout: float | None = None, phrase_limit: float = 15) -> str | None:
        """Record one phrase and return the recognised text (None if nothing understood)."""
        with self.mic as source:
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            except self.sr.WaitTimeoutError:
                return None
        try:
            # Google's free web recogniser; swap for recognize_whisper() for offline use.
            return self.recognizer.recognize_google(audio)
        except self.sr.UnknownValueError:
            return None
        except self.sr.RequestError as exc:
            raise VoiceUnavailable(f"Speech service unreachable: {exc}") from exc

    def say(self, text: str) -> None:
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()


def strip_wake_word(heard: str, wake_word: str) -> str | None:
    """Return the command after the wake word, "" if only the wake word, None if absent."""
    lowered = heard.lower()
    wake = wake_word.lower()
    # Speech recognisers often hear "vector" as similar words.
    variants = {wake, "victor", "vektor", "hey " + wake, "ok " + wake, "okay " + wake}
    for v in sorted(variants, key=len, reverse=True):
        idx = lowered.find(v)
        if idx != -1:
            return heard[idx + len(v):].lstrip(" ,.!?")
    return None

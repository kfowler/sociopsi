"""Audio TTS and sound playback backends for Darwin and Linux."""

import logging
import shutil
import subprocess
import threading

from sociopsi.platform.base import AudioBackend, VoiceInfo

logger = logging.getLogger(__name__)


class DarwinAudioBackend(AudioBackend):
    """macOS audio via NSSpeechSynthesizer and afplay."""

    def speak(self, text: str, voice: str | None = None, rate: int = 200) -> None:
        from AppKit import NSSpeechSynthesizer
        from Foundation import NSDate, NSDefaultRunLoopMode, NSRunLoop

        synth = NSSpeechSynthesizer.alloc().init()

        if voice:
            # Resolve voice name to identifier
            voice_id = self._resolve_voice_id(voice)
            if voice_id:
                synth.setVoice_(voice_id)

        # NSSpeechSynthesizer rate is in words per minute directly
        synth.setRate_(rate)

        done = threading.Event()

        from Foundation import NSObject

        class _Delegate(NSObject):
            def speechSynthesizer_didFinishSpeaking_(self, _sender, _finished):
                done.set()

        delegate = _Delegate.alloc().init()
        synth.setDelegate_(delegate)
        synth.startSpeakingString_(text)

        # Pump run loop while waiting (timeout after 60s to prevent hangs)
        run_loop = NSRunLoop.currentRunLoop()
        elapsed = 0.0
        while not done.is_set() and elapsed < 60.0:
            run_loop.runMode_beforeDate_(
                NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.05)
            )
            elapsed += 0.05

    def play_sound(self, path: str) -> None:
        subprocess.run(["afplay", path], capture_output=True, timeout=30)

    def list_voices(self, language: str = "en") -> list[VoiceInfo]:
        from AppKit import NSSpeechSynthesizer

        result: list[VoiceInfo] = []
        for voice_id in NSSpeechSynthesizer.availableVoices():
            attrs = NSSpeechSynthesizer.attributesForVoice_(voice_id)
            if not attrs:
                continue
            name = attrs.get("VoiceName", "")
            lang = attrs.get("VoiceLanguage", "")
            if not lang.startswith(language):
                continue
            # Determine quality from voice name hints
            quality = 0
            if "(Premium)" in name:
                quality = 3
            elif "(Enhanced)" in name:
                quality = 2
            result.append(VoiceInfo(name=name, identifier=voice_id, language=lang, quality=quality))

        result.sort(key=lambda v: v.quality, reverse=True)
        return result

    def voice_available(self, name: str) -> bool:
        from AppKit import NSSpeechSynthesizer

        for voice_id in NSSpeechSynthesizer.availableVoices():
            attrs = NSSpeechSynthesizer.attributesForVoice_(voice_id)
            if attrs and attrs.get("VoiceName") == name:
                return True
        return False

    def best_voice(self, language: str = "en") -> VoiceInfo | None:
        voices = self.list_voices(language)
        return voices[0] if voices else None

    def _resolve_voice_id(self, name: str) -> str | None:
        """Resolve a voice display name to its system identifier."""
        from AppKit import NSSpeechSynthesizer

        for voice_id in NSSpeechSynthesizer.availableVoices():
            attrs = NSSpeechSynthesizer.attributesForVoice_(voice_id)
            if attrs and attrs.get("VoiceName") == name:
                return voice_id

        # Try partial match (e.g. "Zoe" matches "Zoe (Premium)")
        base_name = name.split("(")[0].strip()
        for voice_id in NSSpeechSynthesizer.availableVoices():
            attrs = NSSpeechSynthesizer.attributesForVoice_(voice_id)
            if attrs and base_name in attrs.get("VoiceName", ""):
                return voice_id

        return None


class LinuxAudioBackend(AudioBackend):
    """Linux audio via pyttsx3/espeak-ng and paplay/aplay/mpv."""

    def speak(self, text: str, voice: str | None = None, rate: int = 200) -> None:
        # Try pyttsx3 first (provides best cross-distro support)
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            if voice:
                # Try to find matching voice
                for v in engine.getProperty("voices"):
                    if voice.lower() in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
            engine.say(text)
            engine.runAndWait()
            return
        except Exception:
            pass

        # Fallback: espeak-ng directly
        cmd = ["espeak-ng"]
        if rate:
            cmd.extend(["-s", str(rate)])
        if voice:
            cmd.extend(["-v", voice])
        cmd.append(text)

        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
        except FileNotFoundError:
            # Last resort: espeak (older)
            cmd[0] = "espeak"
            subprocess.run(cmd, capture_output=True, timeout=60)

    def play_sound(self, path: str) -> None:
        # Try players in order of preference
        for player in ["paplay", "aplay", "mpv"]:
            if shutil.which(player):
                args = [player]
                if player == "mpv":
                    args.extend(["--no-video", "--really-quiet"])
                args.append(path)
                subprocess.run(args, capture_output=True, timeout=30)
                return
        logger.warning("No audio player found (tried paplay, aplay, mpv)")

    def list_voices(self, language: str = "en") -> list[VoiceInfo]:
        result: list[VoiceInfo] = []

        # Try pyttsx3 first
        try:
            import pyttsx3

            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                # pyttsx3 voice languages vary by backend
                lang_ids = v.languages
                lang_str = lang_ids[0] if lang_ids else ""
                if isinstance(lang_str, bytes):
                    lang_str = lang_str.decode("utf-8", errors="replace")
                if language and not lang_str.lower().startswith(language.lower()):
                    continue
                result.append(VoiceInfo(name=v.name, identifier=v.id, language=lang_str, quality=1))
            return result
        except Exception:
            pass

        # Fallback: parse espeak-ng --voices
        try:
            proc = subprocess.run(
                ["espeak-ng", "--voices=" + language],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in proc.stdout.strip().split("\n")[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    lang = parts[1]
                    name = parts[3]
                    result.append(VoiceInfo(name=name, identifier=name, language=lang, quality=0))
        except FileNotFoundError, subprocess.TimeoutExpired:
            pass

        return result

    def voice_available(self, name: str) -> bool:
        for v in self.list_voices():
            if v.name == name:
                return True
        return False

    def best_voice(self, language: str = "en") -> VoiceInfo | None:
        voices = self.list_voices(language)
        return voices[0] if voices else None

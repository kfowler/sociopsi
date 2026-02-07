"""Communication actions: notify, speak, display, sounds."""

import subprocess
from typing import Any

from sociopsi.platform import get_notification_backend


def notify(message: str, title: str | None = None, duration: int = 30) -> dict[str, Any]:
    """Send a notification dialog that can be dismissed."""
    title = title or "Socio-Psi"

    backend = get_notification_backend()
    result = backend.notify(title, message, duration)
    if "error" not in result:
        acknowledged = result.get("acknowledged", False)
        result["description"] = (
            "acknowledged by User" if acknowledged else "notification shown, no response"
        )
    else:
        result["description"] = "could not notify"
    return result


def _get_best_voice(language: str = "en-US") -> tuple[str | None, str]:
    """Get the highest quality voice available for a language.

    Returns (voice_identifier, voice_name) or (None, "default") if no premium voice found.
    Priority: Premium (quality 3) > Enhanced (quality 2)
    """
    try:
        import AVFoundation  # type: ignore[import-untyped]

        voices = AVFoundation.AVSpeechSynthesisVoice.speechVoices()  # type: ignore[attr-defined]
        best_voice = None
        best_quality = 0
        best_name = "default"

        for v in voices:
            lang = v.language()
            if not lang.startswith(language.split("-")[0]):  # Match language family
                continue

            quality = v.quality()
            if quality > best_quality:
                best_quality = quality
                best_voice = v.identifier()
                best_name = v.name()

        return (best_voice, best_name)
    except ImportError:
        return (None, "default")


def speak(text: str, voice: str | None = None, rate: int | None = None) -> dict[str, Any]:
    """Speak text aloud via the voice queue (non-blocking) or directly (blocking fallback).

    Uses the holistic self voice by default.

    Args:
        text: The text to speak
        voice: Optional voice name. If not specified, uses the self voice.
        rate: Speech rate in words per minute. If not specified, uses config rate.
    """
    from sociopsi.voice import get_voice, queue_speech

    # Use self voice and config rate as defaults
    v = get_voice()
    if v is not None:
        voice = voice or v.config.voice_self
        rate = rate or v.config.voice_rate

    speech_rate = rate or 200

    # Try to use the voice queue (non-blocking)
    if queue_speech(text, voice, speech_rate):
        return {
            "spoken": True,
            "queued": True,
            "text": text,
            "description": "speech queued",
        }

    # Fallback: speak directly (blocking) if no voice instance
    return _speak_direct(text, voice, speech_rate)


def _speak_direct(text: str, voice: str | None = None, rate: int = 200) -> dict[str, Any]:
    """Speak directly using AVFoundation (blocking). Used as fallback."""
    try:
        import threading

        import AVFoundation  # type: ignore[import-untyped]

        # Convert WPM to AVSpeechSynthesizer rate (0.0-1.0)
        av_rate = max(0.0, min(1.0, (rate - 90) / 420))

        # Select best voice if not specified
        voice_name = "default"
        if not voice:
            _, voice_name = _get_best_voice("en-US")
            # Get voice by name
            voices = AVFoundation.AVSpeechSynthesisVoice.speechVoices()  # type: ignore[attr-defined]
            for v in voices:
                if v.name() == voice_name:
                    voice = v.identifier()
                    break

        # Create utterance
        utterance = AVFoundation.AVSpeechUtterance.speechUtteranceWithString_(text)  # type: ignore[attr-defined]
        utterance.setRate_(av_rate)
        utterance.setPitchMultiplier_(1.0)
        utterance.setVolume_(1.0)

        # Set voice
        if voice:
            av_voice = AVFoundation.AVSpeechSynthesisVoice.voiceWithIdentifier_(voice)  # type: ignore[attr-defined]
            if av_voice:
                utterance.setVoice_(av_voice)
                voice_name = av_voice.name()

        # Create synthesizer and speak
        synthesizer = AVFoundation.AVSpeechSynthesizer.alloc().init()  # type: ignore[attr-defined]

        # Use threading event to wait for completion
        done_event = threading.Event()

        class SpeechDelegate:
            def speechSynthesizer_didFinishSpeechUtterance_(self, synth, utt):
                done_event.set()

            def speechSynthesizer_didCancelSpeechUtterance_(self, synth, utt):
                done_event.set()

        delegate = SpeechDelegate()
        synthesizer.setDelegate_(delegate)
        synthesizer.speakUtterance_(utterance)

        # Wait for speech to complete (max 60 seconds)
        done_event.wait(timeout=60)

        return {
            "spoken": True,
            "queued": False,
            "text": text,
            "voice": voice_name,
            "description": "words spoken aloud",
        }

    except ImportError:
        return {
            "error": "AVFoundation not available",
            "description": "could not speak",
        }

    except Exception as e:
        return {"error": str(e), "description": "could not speak"}


def display_message(text: str, duration: int | None = None) -> dict[str, Any]:
    """Display a message on screen."""
    duration = duration or 5

    backend = get_notification_backend()
    result = backend.display_message(text, duration)
    if "error" not in result:
        acknowledged = result.get("acknowledged", False)
        result["description"] = (
            "acknowledged by User" if acknowledged else "message shown, no response"
        )
    else:
        result["description"] = "could not display message"
    return result


def play_sound(sound: str) -> dict[str, Any]:
    """Play a sound."""
    # Built-in sounds
    builtin_sounds = {
        "chime": "/System/Library/Sounds/Glass.aiff",
        "alert": "/System/Library/Sounds/Sosumi.aiff",
        "heartbeat": "/System/Library/Sounds/Tink.aiff",  # Closest built-in
        "ping": "/System/Library/Sounds/Ping.aiff",
        "pop": "/System/Library/Sounds/Pop.aiff",
        "purr": "/System/Library/Sounds/Purr.aiff",
        "submarine": "/System/Library/Sounds/Submarine.aiff",
    }

    sound_path = builtin_sounds.get(sound, sound)

    try:
        subprocess.run(
            ["afplay", sound_path],
            capture_output=True,
            timeout=10,
        )
        return {
            "played": True,
            "sound": sound,
            "description": f"sound: {sound}",
        }
    except Exception as e:
        return {"error": str(e), "description": f"could not play {sound}"}


def play_music(query: str | None = None, file: str | None = None) -> dict[str, Any]:
    """Play music via Music app or file."""
    try:
        if file:
            subprocess.run(
                ["afplay", file],
                capture_output=True,
                timeout=300,
            )
            return {"playing": True, "file": file, "description": "playing audio file"}
        elif query:
            script = f'''
            tell application "Music"
                play (first track whose name contains "{query}")
            end tell
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
            )
            return {"playing": True, "query": query, "description": f"playing: {query}"}
        else:
            return {"error": "no query or file specified", "description": "nothing to play"}
    except Exception as e:
        return {"error": str(e), "description": "could not play music"}

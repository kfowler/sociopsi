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
    """Speak directly using platform audio backend (blocking). Used as fallback."""
    try:
        from sociopsi.platform import get_audio_backend

        audio = get_audio_backend()

        # Select best voice if not specified
        voice_name = voice or "default"
        if not voice:
            best = audio.best_voice("en")
            if best:
                voice_name = best.name

        audio.speak(text, voice=voice_name, rate=rate)

        return {
            "spoken": True,
            "queued": False,
            "text": text,
            "voice": voice_name,
            "description": "words spoken aloud",
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
    import sys

    # Built-in sounds (platform-specific paths)
    if sys.platform == "darwin":
        builtin_sounds = {
            "chime": "/System/Library/Sounds/Glass.aiff",
            "alert": "/System/Library/Sounds/Sosumi.aiff",
            "heartbeat": "/System/Library/Sounds/Tink.aiff",
            "ping": "/System/Library/Sounds/Ping.aiff",
            "pop": "/System/Library/Sounds/Pop.aiff",
            "purr": "/System/Library/Sounds/Purr.aiff",
            "submarine": "/System/Library/Sounds/Submarine.aiff",
        }
    else:
        builtin_sounds = {
            "chime": "/usr/share/sounds/freedesktop/stereo/complete.oga",
            "alert": "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga",
            "heartbeat": "/usr/share/sounds/freedesktop/stereo/message.oga",
            "ping": "/usr/share/sounds/freedesktop/stereo/bell.oga",
            "pop": "/usr/share/sounds/freedesktop/stereo/button-pressed.oga",
            "purr": "/usr/share/sounds/freedesktop/stereo/message.oga",
            "submarine": "/usr/share/sounds/freedesktop/stereo/suspend-error.oga",
        }

    sound_path = builtin_sounds.get(sound, sound)

    try:
        from sociopsi.platform import get_audio_backend

        audio = get_audio_backend()
        audio.play_sound(sound_path)
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
            from sociopsi.platform import get_audio_backend

            audio = get_audio_backend()
            audio.play_sound(file)
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

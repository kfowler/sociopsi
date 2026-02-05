"""Communication actions: notify, speak, display, sounds."""

import subprocess
from typing import Any


def notify(message: str, title: str | None = None, duration: int = 30) -> dict[str, Any]:
    """Send a notification dialog that can be dismissed."""
    title = title or "Jung"

    try:
        script = f'''
        tell application "System Events"
            display dialog "{message}" with title "{title}" buttons {{"OK"}} giving up after {duration}
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=duration + 5,
        )
        # Check if user clicked OK vs dialog timed out
        acknowledged = "gave up:true" not in result.stdout.lower()
        return {
            "sent": True,
            "acknowledged": acknowledged,
            "title": title,
            "message": message,
            "description": "acknowledged by User"
            if acknowledged
            else "notification shown, no response",
        }
    except Exception as e:
        return {"error": str(e), "description": "could not notify"}


def speak(text: str, voice: str | None = None) -> dict[str, Any]:
    """Speak text aloud using text-to-speech."""
    try:
        cmd = ["say"]
        if voice:
            cmd.extend(["-v", voice])
        cmd.append(text)

        subprocess.run(cmd, capture_output=True, timeout=30)
        return {
            "spoken": True,
            "text": text,
            "voice": voice or "default",
            "description": "words spoken aloud",
        }
    except Exception as e:
        return {"error": str(e), "description": "could not speak"}


def display_message(text: str, duration: int | None = None) -> dict[str, Any]:
    """Display a message on screen."""
    duration = duration or 5

    try:
        script = f'''
        tell application "System Events"
            display dialog "{text}" buttons {{"OK"}} giving up after {duration}
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=duration + 5,
        )
        # Check if user clicked OK vs dialog timed out
        # AppleScript returns "gave up:true" when it times out
        acknowledged = "gave up:true" not in result.stdout.lower()
        return {
            "displayed": True,
            "acknowledged": acknowledged,
            "text": text,
            "duration": duration,
            "description": "acknowledged by User" if acknowledged else "message shown, no response",
        }
    except Exception as e:
        return {"error": str(e), "description": "could not display message"}


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

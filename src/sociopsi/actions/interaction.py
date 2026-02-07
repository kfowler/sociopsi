"""Interaction actions: message, type, click."""

import subprocess
from typing import Any


def send_message(message: str, to: str | None = None) -> dict[str, Any]:
    """Send an iMessage to user or contact."""
    try:
        # If no recipient specified, try to send to the logged-in user
        if to is None:
            # Get current user's Apple ID or phone (this is tricky)
            # For now, require explicit recipient
            return {
                "error": "Recipient required",
                "description": "Need a phone number or email to send message",
            }

        # Escape message for AppleScript
        escaped_message = message.replace('"', '\\"').replace("'", "\\'")
        escaped_to = to.replace('"', '\\"')

        script = f'''
        tell application "Messages"
            set targetService to 1st account whose service type = iMessage
            set targetBuddy to participant "{escaped_to}" of targetService
            send "{escaped_message}" to targetBuddy
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return {
                "sent": True,
                "to": to,
                "message": message,
                "description": f"Message sent to {to}",
            }
        else:
            return {
                "sent": False,
                "error": result.stderr or "Send failed",
                "description": "Could not send message",
            }

    except Exception as e:
        return {"error": str(e), "description": f"Message failed: {e}"}


def type_text(text: str, delay: float = 0.05) -> dict[str, Any]:
    """Type text into the currently active application."""
    try:
        # Escape text for AppleScript
        escaped_text = text.replace('"', '\\"').replace("\\", "\\\\")

        # Use System Events to type
        script = f'''
        tell application "System Events"
            keystroke "{escaped_text}"
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {
                "typed": True,
                "text": text[:50] + "..." if len(text) > 50 else text,
                "length": len(text),
                "description": f"Typed {len(text)} characters",
            }
        else:
            return {
                "typed": False,
                "error": result.stderr,
                "description": "Could not type text",
            }

    except Exception as e:
        return {"error": str(e), "description": f"Typing failed: {e}"}

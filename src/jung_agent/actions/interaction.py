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


def click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    """Click at screen coordinates."""
    try:
        # Determine click type
        if button == "right":
            click_cmd = "click 2"
        elif button == "double":
            click_cmd = "double click"
        else:
            click_cmd = "click"

        script = f"""
        tell application "System Events"
            {click_cmd} at {{{x}, {y}}}
        end tell
        """

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return {
                "clicked": True,
                "x": x,
                "y": y,
                "button": button,
                "description": f"Clicked at ({x}, {y})",
            }
        else:
            # Try using cliclick if available
            try:
                click_type = "rc" if button == "right" else "dc" if button == "double" else "c"
                subprocess.run(
                    ["cliclick", f"{click_type}:{x},{y}"],
                    capture_output=True,
                    timeout=5,
                )
                return {
                    "clicked": True,
                    "x": x,
                    "y": y,
                    "button": button,
                    "description": f"Clicked at ({x}, {y})",
                }
            except FileNotFoundError:
                return {
                    "clicked": False,
                    "error": "Click failed - try installing cliclick",
                    "description": "Could not click",
                }

    except Exception as e:
        return {"error": str(e), "description": f"Click failed: {e}"}


def move_mouse(x: int, y: int) -> dict[str, Any]:
    """Move mouse to screen coordinates."""
    try:
        # AppleScript can't easily move mouse, use cliclick
        try:
            subprocess.run(
                ["cliclick", f"m:{x},{y}"],
                capture_output=True,
                timeout=5,
            )
            return {
                "moved": True,
                "x": x,
                "y": y,
                "description": f"Mouse moved to ({x}, {y})",
            }
        except FileNotFoundError:
            return {
                "moved": False,
                "error": "Install cliclick for mouse control: brew install cliclick",
                "description": "Could not move mouse",
            }

    except Exception as e:
        return {"error": str(e), "description": f"Mouse move failed: {e}"}


def press_key(key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
    """Press a keyboard key with optional modifiers."""
    try:
        # Map common key names to AppleScript key codes
        key_map = {
            "return": "return",
            "enter": "return",
            "tab": "tab",
            "escape": "escape",
            "esc": "escape",
            "space": "space",
            "delete": "delete",
            "backspace": "delete",
            "up": "up arrow",
            "down": "down arrow",
            "left": "left arrow",
            "right": "right arrow",
        }

        as_key = key_map.get(key.lower(), key)

        # Build modifier string
        mod_str = ""
        if modifiers:
            mod_parts = []
            for mod in modifiers:
                if mod.lower() in ("cmd", "command"):
                    mod_parts.append("command down")
                elif mod.lower() in ("shift",):
                    mod_parts.append("shift down")
                elif mod.lower() in ("opt", "option", "alt"):
                    mod_parts.append("option down")
                elif mod.lower() in ("ctrl", "control"):
                    mod_parts.append("control down")
            if mod_parts:
                mod_str = " using {" + ", ".join(mod_parts) + "}"

        script = f"""
        tell application "System Events"
            key code {as_key}{mod_str}
        end tell
        """

        # For simple keys, use keystroke
        if as_key == key and len(key) == 1:
            script = f'''
            tell application "System Events"
                keystroke "{key}"{mod_str}
            end tell
            '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return {
            "pressed": result.returncode == 0,
            "key": key,
            "modifiers": modifiers,
            "description": f"Pressed {'+'.join(modifiers or []) + '+' if modifiers else ''}{key}",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Key press failed: {e}"}

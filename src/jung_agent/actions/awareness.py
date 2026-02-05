"""Awareness actions: time, weather, screen, clipboard, calendar."""

import subprocess
from datetime import datetime
from typing import Any


def check_time(**kwargs: Any) -> dict[str, Any]:
    """Check current time and temporal context."""
    now = datetime.now()
    hour = now.hour

    # Determine time of day
    if 5 <= hour < 12:
        period = "morning"
        feeling = "awakening"
    elif 12 <= hour < 17:
        period = "afternoon"
        feeling = "active"
    elif 17 <= hour < 21:
        period = "evening"
        feeling = "winding down"
    else:
        period = "night"
        feeling = "quiet, should rest"

    # Day of week context
    day_name = now.strftime("%A")
    is_weekend = now.weekday() >= 5

    return {
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "day": day_name,
        "period": period,
        "hour": hour,
        "is_weekend": is_weekend,
        "description": f"{period}, {now.strftime('%H:%M')} on {day_name}. {feeling}",
    }


def check_weather(location: str | None = None) -> dict[str, Any]:
    """Check weather conditions via wttr.in."""
    try:
        # Use wttr.in for simple weather data
        loc = location or ""
        result = subprocess.run(
            ["curl", "-s", f"https://wttr.in/{loc}?format=%C|%t|%h|%w"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            if len(parts) >= 4:
                condition, temp, humidity, wind = parts[:4]
                return {
                    "condition": condition.strip(),
                    "temperature": temp.strip(),
                    "humidity": humidity.strip(),
                    "wind": wind.strip(),
                    "location": location or "current",
                    "description": f"{condition.strip()}, {temp.strip()}, humidity {humidity.strip()}",
                }

        return {
            "error": "Could not parse weather",
            "description": "Weather unknown",
        }

    except Exception as e:
        return {"error": str(e), "description": "Could not check weather"}


def take_screenshot(**kwargs: Any) -> dict[str, Any]:
    """Capture screenshot of current screen."""
    import base64
    import tempfile
    from pathlib import Path

    try:
        # Create temp file for screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        # Use screencapture on macOS
        result = subprocess.run(
            ["screencapture", "-x", temp_path],
            capture_output=True,
            timeout=5,
        )

        if result.returncode != 0:
            return {"error": "Screenshot failed", "description": "Could not capture screen"}

        # Read and encode the image
        with open(temp_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        # Get image size
        size = Path(temp_path).stat().st_size

        # Try to describe with vision model if available
        description = _describe_screenshot(temp_path)

        Path(temp_path).unlink()

        return {
            "status": "captured",
            "size_bytes": size,
            "data": image_data[:100] + "...",
            "full_data": image_data,
            "description": description or "Screen captured",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Screenshot failed: {e}"}


def _describe_screenshot(image_path: str) -> str | None:
    """Use vision model to describe screenshot."""
    try:
        check_result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "llava" not in check_result.stdout.lower():
            return None

        import ollama

        response = ollama.chat(
            model="llava",
            messages=[
                {
                    "role": "user",
                    "content": "Briefly describe what's on this screen (1-2 sentences). What app or content is visible?",
                    "images": [image_path],
                }
            ],
        )

        return response["message"]["content"]

    except Exception:
        return None


def read_clipboard(**kwargs: Any) -> dict[str, Any]:
    """Read current clipboard contents."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            content = result.stdout
            # Truncate if too long
            preview = content[:500] + "..." if len(content) > 500 else content
            content_type = "text"

            # Check if it's a URL
            if content.strip().startswith(("http://", "https://")):
                content_type = "url"
            # Check if it might be code
            elif any(
                kw in content for kw in ["def ", "function ", "class ", "import ", "const ", "let "]
            ):
                content_type = "code"

            return {
                "content": preview,
                "full_content": content,
                "length": len(content),
                "type": content_type,
                "description": f"Clipboard contains {content_type} ({len(content)} chars)",
            }

        return {"content": "", "description": "Clipboard empty"}

    except Exception as e:
        return {"error": str(e), "description": "Could not read clipboard"}


def check_calendar(days: int = 1) -> dict[str, Any]:
    """Check upcoming calendar events."""
    try:
        # Use AppleScript to get calendar events
        script = f"""
        set output to ""
        set today to current date
        set endDate to today + ({days} * days)

        tell application "Calendar"
            set allEvents to {{}}
            repeat with cal in calendars
                set calEvents to (every event of cal whose start date >= today and start date <= endDate)
                repeat with evt in calEvents
                    set evtStart to start date of evt
                    set evtName to summary of evt
                    set output to output & (evtStart as string) & " | " & evtName & linefeed
                end repeat
            end repeat
        end tell

        return output
        """

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        events = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 1)
                    if len(parts) == 2:
                        events.append(
                            {
                                "time": parts[0].strip(),
                                "title": parts[1].strip(),
                            }
                        )

        if events:
            next_event = events[0]["title"]
            return {
                "events": events,
                "count": len(events),
                "description": f"{len(events)} upcoming: next is '{next_event}'",
            }
        else:
            return {
                "events": [],
                "count": 0,
                "description": "No upcoming events, schedule is clear",
            }

    except Exception as e:
        return {"error": str(e), "description": "Could not check calendar"}

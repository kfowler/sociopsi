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
    """Capture screenshot of current screen and analyze what user is doing."""
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
        analysis = _analyze_screenshot(temp_path)

        Path(temp_path).unlink()

        result_dict: dict[str, Any] = {
            "status": "captured",
            "size_bytes": size,
            "data": image_data[:100] + "...",
            "full_data": image_data,
        }

        if analysis:
            result_dict.update(analysis)
        else:
            result_dict["description"] = "Screen captured"

        return result_dict

    except Exception as e:
        return {"error": str(e), "description": f"Screenshot failed: {e}"}


def _analyze_screenshot(image_path: str) -> dict[str, Any] | None:
    """Use vision model to analyze screenshot and extract structured info."""
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

        # Structured prompt for better extraction
        prompt = """Analyze this screenshot and answer:
1. APP: What application is in focus? (e.g., Terminal, VS Code, Safari, Chrome, Slack)
2. ACTIVITY: What is the user doing? (e.g., coding, browsing, writing, chatting, watching video)
3. CONTENT: Brief description of what's on screen (1 sentence)
4. MOOD: Does the screen suggest focused work, leisure, or communication?

Format your response exactly like:
APP: [app name]
ACTIVITY: [activity]
CONTENT: [description]
MOOD: [work/leisure/communication]"""

        response = ollama.chat(
            model="llava",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_path],
                }
            ],
        )

        content = response["message"]["content"]

        # Parse structured response
        result: dict[str, Any] = {"description": content}

        lines = content.split("\n")
        for line in lines:
            line_lower = line.lower()
            if line_lower.startswith("app:"):
                result["app_name"] = line.split(":", 1)[1].strip()
            elif line_lower.startswith("activity:"):
                result["activity"] = line.split(":", 1)[1].strip()
            elif line_lower.startswith("content:"):
                result["content_summary"] = line.split(":", 1)[1].strip()
            elif line_lower.startswith("mood:"):
                result["mood"] = line.split(":", 1)[1].strip()

        return result

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

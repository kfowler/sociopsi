"""Learning actions: web search, reading, vision, transcription."""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus


def web_search(query: str) -> dict[str, Any]:
    """Search the web and return results."""
    encoded_query = quote_plus(query)

    # Try Wikipedia API first (most reliable)
    try:
        result = subprocess.run(
            [
                "curl", "-s",
                f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_query}&limit=5&format=json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            if len(data) >= 4 and data[1]:
                titles, descriptions, urls = data[1], data[2], data[3]
                results = []
                for i, title in enumerate(titles):
                    results.append({
                        "title": title,
                        "url": urls[i] if i < len(urls) else "",
                        "abstract": descriptions[i] if i < len(descriptions) else "",
                    })

                if results:
                    return {
                        "query": query,
                        "source": "wikipedia",
                        "results": results,
                        "count": len(results),
                        "description": f"Found {len(results)} results for '{query}'",
                    }
    except Exception:
        pass

    # Try ddgr if available
    try:
        result = subprocess.run(
            ["ddgr", "--json", "-n", "5", query],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip() not in ("[]", ""):
            results = json.loads(result.stdout)
            if results:
                return {
                    "query": query,
                    "source": "duckduckgo",
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "abstract": r.get("abstract", ""),
                        }
                        for r in results[:5]
                    ],
                    "count": len(results),
                    "description": f"Found {len(results)} results for '{query}'",
                }
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: Brave Search (no API key needed for limited use)
    try:
        result = subprocess.run(
            [
                "curl", "-s",
                "-H", "Accept: application/json",
                f"https://search.brave.com/api/suggest?q={encoded_query}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            suggestions = data.get("results", []) or data.get("suggestions", [])
            if suggestions:
                results = [{"title": s, "url": "", "abstract": ""} for s in suggestions[:5]]
                return {
                    "query": query,
                    "source": "brave_suggest",
                    "results": results,
                    "count": len(results),
                    "description": f"Found {len(results)} suggestions for '{query}'",
                }
    except Exception:
        pass

    return {
        "query": query,
        "error": "All search providers failed",
        "results": [],
        "count": 0,
        "description": f"Could not find results for '{query}'",
    }


def web_read(url: str) -> dict[str, Any]:
    """Read and extract content from a webpage."""
    try:
        # Use curl to fetch the page
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-L",  # Follow redirects
                "-A", "Mozilla/5.0",
                "--max-time", "30",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=35,
        )

        if result.returncode != 0:
            return {"url": url, "error": "Failed to fetch", "description": "Could not read the page"}

        html = result.stdout

        # Extract title
        title_match = re.search(r"<title[^>]*>([^<]*)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Unknown"

        # Remove script and style content
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Decode HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')

        # Truncate to reasonable length
        max_length = 4000
        if len(text) > max_length:
            text = text[:max_length] + "... [truncated]"

        return {
            "url": url,
            "title": title,
            "content": text,
            "length": len(text),
            "description": f"Read '{title}' ({len(text)} chars)",
        }

    except subprocess.TimeoutExpired:
        return {"url": url, "error": "timeout", "description": "Page load timed out"}
    except Exception as e:
        return {"url": url, "error": str(e), "description": f"Failed to read: {e}"}


def describe_image(prompt: str | None = None) -> dict[str, Any]:
    """Capture an image from the camera and describe it using vision."""
    from jung_agent.sensors import external

    try:
        # Capture image using opencv
        capture = external.capture_camera(0.5)

        if capture.get("status") != "captured":
            return {
                "error": capture.get("error", "Camera capture failed"),
                "description": capture.get("description", "Could not capture image from camera"),
            }

        # Save full image data to temp file for vision model
        import base64
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
            f.write(base64.b64decode(capture["full_data"]))

        # Try to use ollama with a vision model if available
        try:
            check_result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            has_vision = "llava" in check_result.stdout.lower()

            if has_vision:
                default_prompt = (
                    "This is what I am seeing right now through my camera in real time. "
                    "Describe what I see in detail."
                )
                vision_prompt = prompt or default_prompt

                import ollama as ollama_client
                response = ollama_client.chat(
                    model="llava",
                    messages=[{
                        "role": "user",
                        "content": vision_prompt,
                        "images": [temp_path],
                    }],
                )

                description = response["message"]["content"]
                Path(temp_path).unlink()

                return {
                    "captured": True,
                    "width": capture.get("width"),
                    "height": capture.get("height"),
                    "description": description,
                    "prompt": vision_prompt,
                }
        except Exception:
            pass

        Path(temp_path).unlink()
        return {
            "captured": True,
            "width": capture.get("width"),
            "height": capture.get("height"),
            "description": f"Captured {capture.get('width')}x{capture.get('height')} image but no vision model available. Install: ollama pull llava",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Vision failed: {e}"}


def transcribe_audio(duration: float = 5.0) -> dict[str, Any]:
    """Record audio and transcribe speech."""
    from jung_agent.sensors import external

    try:
        # Record audio using sounddevice
        capture = external.capture_audio(duration)

        if capture.get("status") != "captured":
            return {
                "error": capture.get("error", "Recording failed"),
                "description": capture.get("description", "Could not record audio from microphone"),
            }

        temp_path = capture.get("temp_path")
        if not temp_path or not Path(temp_path).exists():
            return {
                "error": "No audio file",
                "description": "Audio captured but file not available",
            }

        # Try to use whisper for transcription if available
        try:
            result = subprocess.run(
                ["whisper", temp_path, "--model", "tiny", "--output_format", "txt", "--output_dir", "/tmp"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            txt_path = Path("/tmp") / (Path(temp_path).stem + ".txt")
            if txt_path.exists():
                transcription = txt_path.read_text().strip()
                txt_path.unlink()
                Path(temp_path).unlink()

                return {
                    "duration": duration,
                    "rms_level": capture.get("rms_level"),
                    "transcription": transcription,
                    "description": f"Heard: {transcription[:100]}..." if len(transcription) > 100 else f"Heard: {transcription}",
                }
        except FileNotFoundError:
            pass

        # No whisper available - return audio info
        Path(temp_path).unlink()
        return {
            "duration": duration,
            "recorded": True,
            "rms_level": capture.get("rms_level"),
            "audio_description": capture.get("description"),
            "description": f"Recorded {duration}s of audio ({capture.get('description')}). Install whisper for transcription: brew install openai-whisper",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Transcription failed: {e}"}

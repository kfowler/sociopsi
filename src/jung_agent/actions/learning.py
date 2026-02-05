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
    try:
        # Use ddgr (DuckDuckGo CLI) if available, otherwise fallback
        encoded_query = quote_plus(query)

        # Try ddgr first (brew install ddgr)
        try:
            result = subprocess.run(
                ["ddgr", "--json", "-n", "5", query],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                results = json.loads(result.stdout)
                return {
                    "query": query,
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
        except FileNotFoundError:
            pass

        # Fallback: use curl with DuckDuckGo HTML API
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-A", "Mozilla/5.0",
                f"https://html.duckduckgo.com/html/?q={encoded_query}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Parse simple results from HTML
            html = result.stdout
            results = []

            # Extract result snippets (simplified parsing)
            for match in re.finditer(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?'
                r'class="result__snippet"[^>]*>([^<]*)<',
                html,
                re.DOTALL,
            ):
                url, title, snippet = match.groups()
                # Clean up DuckDuckGo redirect URLs
                if "uddg=" in url:
                    url_match = re.search(r"uddg=([^&]*)", url)
                    if url_match:
                        from urllib.parse import unquote
                        url = unquote(url_match.group(1))

                results.append({
                    "title": title.strip(),
                    "url": url,
                    "abstract": snippet.strip()[:200],
                })
                if len(results) >= 5:
                    break

            return {
                "query": query,
                "results": results,
                "count": len(results),
                "description": f"Found {len(results)} results for '{query}'" if results else "No results found",
            }

        return {"query": query, "error": "Search failed", "description": "Could not search the web"}

    except subprocess.TimeoutExpired:
        return {"query": query, "error": "timeout", "description": "Search timed out"}
    except Exception as e:
        return {"query": query, "error": str(e), "description": f"Search failed: {e}"}


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
    try:
        # Capture image
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        # Use imagesnap to capture (brew install imagesnap)
        result = subprocess.run(
            ["imagesnap", "-w", "0.5", temp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0 or not Path(temp_path).exists():
            return {
                "error": "Camera capture failed",
                "description": "Could not capture image from camera",
            }

        # Check if we have a vision-capable model available
        # For now, we'll use a simple description based on file properties
        # In a full implementation, this would use ollama with llava or similar

        file_size = Path(temp_path).stat().st_size

        # Try to use ollama with a vision model if available
        try:
            # Check if llava is available
            check_result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            has_vision = "llava" in check_result.stdout.lower()

            if has_vision:
                vision_prompt = prompt or "Describe what you see in this image in detail."

                # Use ollama with llava
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
                    "description": description,
                    "prompt": vision_prompt,
                }
        except Exception:
            pass

        Path(temp_path).unlink()
        return {
            "captured": True,
            "file_size": file_size,
            "description": "Image captured but no vision model available to describe it. Install llava: ollama pull llava",
        }

    except FileNotFoundError:
        return {
            "error": "imagesnap not found",
            "description": "Camera not available. Install: brew install imagesnap",
        }
    except Exception as e:
        return {"error": str(e), "description": f"Vision failed: {e}"}


def transcribe_audio(duration: float = 5.0) -> dict[str, Any]:
    """Record audio and transcribe speech."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        # Record audio using sox (brew install sox)
        result = subprocess.run(
            ["rec", "-q", temp_path, "trim", "0", str(duration)],
            capture_output=True,
            text=True,
            timeout=duration + 10,
        )

        if result.returncode != 0 or not Path(temp_path).exists():
            return {
                "error": "Recording failed",
                "description": "Could not record audio from microphone",
            }

        file_size = Path(temp_path).stat().st_size

        # Try to use whisper for transcription if available
        try:
            # Check if whisper CLI is available (brew install openai-whisper)
            subprocess.run(
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
                    "transcription": transcription,
                    "description": f"Heard: {transcription[:100]}..." if len(transcription) > 100 else f"Heard: {transcription}",
                }
        except FileNotFoundError:
            pass

        # Fallback: try macOS built-in speech recognition via AppleScript
        try:
            # This is a simplified approach - full implementation would use SFSpeechRecognizer
            Path(temp_path).unlink()
            return {
                "duration": duration,
                "recorded": True,
                "file_size": file_size,
                "description": "Audio recorded but no transcription available. Install: brew install openai-whisper",
            }
        except Exception:
            pass

        Path(temp_path).unlink()
        return {
            "duration": duration,
            "error": "No transcription service",
            "description": "Audio recorded but could not transcribe",
        }

    except FileNotFoundError:
        return {
            "error": "sox not found",
            "description": "Microphone not available. Install: brew install sox",
        }
    except Exception as e:
        return {"error": str(e), "description": f"Transcription failed: {e}"}

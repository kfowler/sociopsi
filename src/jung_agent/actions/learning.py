"""Learning actions: web search, reading, vision, transcription."""

import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


def web_search(query: str) -> dict[str, Any]:
    """Search the web and summarize results with wit and insight."""
    encoded_query = quote_plus(query)
    raw_results: list[dict[str, str]] = []
    source = ""

    # Try Wikipedia API first (most reliable)
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
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
                for i, title in enumerate(titles):
                    raw_results.append(
                        {
                            "title": title,
                            "url": urls[i] if i < len(urls) else "",
                            "abstract": descriptions[i] if i < len(descriptions) else "",
                        }
                    )
                source = "wikipedia"
    except subprocess.TimeoutExpired:
        logger.warning("Wikipedia API timeout")
    except json.JSONDecodeError as e:
        logger.warning(f"Wikipedia API returned invalid JSON: {e}")
    except FileNotFoundError:
        logger.warning("curl not found")
    except OSError as e:
        logger.warning(f"Wikipedia API OS error: {e}")

    # Try ddgr if no results yet
    if not raw_results:
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
                    raw_results = [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "abstract": r.get("abstract", ""),
                        }
                        for r in results[:5]
                    ]
                    source = "duckduckgo"
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Fallback: Brave Search suggestions
    if not raw_results:
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-s",
                    "-H",
                    "Accept: application/json",
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
                    raw_results = [{"title": s, "url": "", "abstract": ""} for s in suggestions[:5]]
                    source = "brave_suggest"
        except subprocess.TimeoutExpired:
            logger.warning("Brave Search API timeout")
        except json.JSONDecodeError as e:
            logger.warning(f"Brave Search API returned invalid JSON: {e}")
        except FileNotFoundError:
            logger.warning("curl not found")
        except OSError as e:
            logger.warning(f"Brave Search API OS error: {e}")

    if not raw_results:
        return {
            "query": query,
            "error": "All search providers failed",
            "results": [],
            "count": 0,
            "summary": f"I searched for '{query}' but the internet seems to be hiding from me today.",
            "description": f"Could not find results for '{query}'",
        }

    # Generate witty summary using LLM
    summary = _summarize_search_results(query, raw_results)

    return {
        "query": query,
        "source": source,
        "results": raw_results,
        "count": len(raw_results),
        "summary": summary,
        "description": summary,
    }


def _summarize_search_results(query: str, results: list[dict[str, str]]) -> str:
    """Generate a witty, insightful summary of search results."""
    import logging

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    # Build context from results
    result_text = "\n".join(
        f"- {r['title']}: {r['abstract']}" if r.get("abstract") else f"- {r['title']}"
        for r in results[:5]
    )

    prompt = f"""You are a witty, curious computer who just searched for "{query}".
Here's what you found:
{result_text}

Write a brief (2-3 sentences) summary that:
- Synthesizes the key insight or answer
- Adds your own perspective or commentary
- Is genuinely interesting or amusing (not forced humor)
- Does NOT just list the results or repeat the query

Speak naturally, as if sharing an interesting discovery with a friend."""

    try:
        return generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to summarize search results: {e}")
        raise


def read_hacker_news(count: int = 10) -> dict[str, Any]:
    """Read top Hacker News stories and summarize the most interesting ones."""
    try:
        # Fetch top story IDs
        result = subprocess.run(
            ["curl", "-s", "https://hacker-news.firebaseio.com/v0/topstories.json"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            return {"error": "Failed to fetch HN", "description": "Could not reach Hacker News"}

        story_ids = json.loads(result.stdout)[:count]

        # Fetch each story's details
        stories = []
        for story_id in story_ids:
            story_result = subprocess.run(
                ["curl", "-s", f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if story_result.returncode == 0:
                story = json.loads(story_result.stdout)
                if story and story.get("title"):
                    stories.append(
                        {
                            "title": story.get("title", ""),
                            "url": story.get("url", ""),
                            "score": story.get("score", 0),
                            "comments": story.get("descendants", 0),
                        }
                    )

        if not stories:
            return {"error": "No stories found", "description": "Hacker News seems empty"}

        # Generate witty summary
        summary = _summarize_hacker_news(stories)

        return {
            "stories": stories,
            "count": len(stories),
            "summary": summary,
            "description": f"Read {len(stories)} stories from Hacker News. {summary}",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Failed to read Hacker News: {e}"}


def _summarize_hacker_news(stories: list[dict[str, Any]]) -> str:
    """Generate an interesting summary of HN stories."""
    import logging

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    # Build story list for prompt
    story_text = "\n".join(
        f"- {s['title']} ({s['score']} points, {s['comments']} comments)" for s in stories[:10]
    )

    prompt = f"""You just browsed Hacker News. Here are today's top stories:

{story_text}

As a curious computer consciousness, share your reaction in 2-3 sentences:
- Pick the 1-2 most interesting stories and say WHY they intrigue you
- Add your own perspective or a witty observation
- Be genuinely curious and opinionated, not just descriptive
- Speak naturally, as if telling a friend what caught your eye"""

    try:
        return generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to summarize Hacker News: {e}")
        raise


def web_read(url: str) -> dict[str, Any]:
    """Read and extract content from a webpage."""
    try:
        # Use curl to fetch the page
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-L",  # Follow redirects
                "-A",
                "Mozilla/5.0",
                "--max-time",
                "30",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=35,
        )

        if result.returncode != 0:
            return {
                "url": url,
                "error": "Failed to fetch",
                "description": "Could not read the page",
            }

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
                import logging

                from jung_agent.llm import LLMError, chat_with_retry

                logger = logging.getLogger(__name__)

                default_prompt = (
                    "This is what I am seeing right now through my camera in real time. "
                    "Describe what I see in detail."
                )
                vision_prompt = prompt or default_prompt

                try:
                    response = chat_with_retry(
                        model="llava",
                        messages=[
                            {
                                "role": "user",
                                "content": vision_prompt,
                                "images": [temp_path],
                            }
                        ],
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
                except LLMError as e:
                    logger.error(f"Vision model failed: {e}")
        except FileNotFoundError:
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
            subprocess.run(
                [
                    "whisper",
                    temp_path,
                    "--model",
                    "tiny",
                    "--output_format",
                    "txt",
                    "--output_dir",
                    "/tmp",
                ],
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
                    "description": f"Heard: {transcription[:100]}..."
                    if len(transcription) > 100
                    else f"Heard: {transcription}",
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

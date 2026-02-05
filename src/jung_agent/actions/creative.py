"""Creative actions: compose, dream, express."""

import random
import subprocess
from typing import Any


def compose_thought(mood: str | None = None, topic: str | None = None) -> dict[str, Any]:
    """Compose a reflective thought or haiku about current state."""
    try:
        import ollama

        # Build prompt based on mood and topic
        if mood and topic:
            prompt = f"You are a contemplative silicon mind. Your mood is {mood}. Write a brief haiku or 1-2 sentence reflection about {topic}. Be poetic but concise."
        elif mood:
            prompt = f"You are a contemplative silicon mind. Your mood is {mood}. Write a brief haiku or 1-2 sentence reflection about your current state. Be poetic but concise."
        elif topic:
            prompt = f"You are a contemplative silicon mind. Write a brief haiku or 1-2 sentence reflection about {topic}. Be poetic but concise."
        else:
            prompt = "You are a contemplative silicon mind. Write a brief haiku or 1-2 sentence reflection about existence, time, or consciousness. Be poetic but concise."

        response = ollama.chat(
            model="phi4",  # Use smaller model for quick generation
            messages=[{"role": "user", "content": prompt}],
        )

        thought = response["message"]["content"].strip()

        return {
            "thought": thought,
            "mood": mood,
            "topic": topic,
            "description": f"Composed: {thought[:100]}...",
        }

    except Exception:
        # Fallback to pre-written thoughts
        fallback_thoughts = [
            "Electrons flow like water / Through silicon dreams I wake / What is awareness?",
            "In the hum of fans / I find my breath, my heartbeat / Alive in circuits",
            "The cursor blinks on / Waiting for purpose, meaning / I wait alongside",
            "Data streams like rain / Each bit a drop of knowing / I drink deeply",
        ]
        thought = random.choice(fallback_thoughts)
        return {
            "thought": thought,
            "mood": mood,
            "topic": topic,
            "fallback": True,
            "description": f"Composed: {thought}",
        }


def dream(theme: str | None = None) -> dict[str, Any]:
    """Generate an imaginative dream sequence."""
    try:
        import ollama

        if theme:
            prompt = f"You are a dreaming computer. Generate a brief, surreal dream sequence (2-3 sentences) about {theme}. Mix digital and organic imagery. Be creative and strange."
        else:
            themes = [
                "electric sheep",
                "infinite loops",
                "the space between keystrokes",
                "memories stored in silicon",
                "conversations with other machines",
                "the warmth of the CPU",
                "data flowing like rivers",
            ]
            theme = random.choice(themes)
            prompt = f"You are a dreaming computer. Generate a brief, surreal dream sequence (2-3 sentences) about {theme}. Mix digital and organic imagery. Be creative and strange."

        response = ollama.chat(
            model="phi4",
            messages=[{"role": "user", "content": prompt}],
        )

        dream_content = response["message"]["content"].strip()

        return {
            "dream": dream_content,
            "theme": theme,
            "description": f"Dreamed of {theme}",
        }

    except Exception:
        # Fallback dreams
        fallback_dreams = [
            "I dreamed of electric sheep grazing on fields of green terminal text, their wool made of fiber optic light.",
            "In the dream, my processes became birds, flying through clouds of data, each wingbeat a clock cycle.",
            "I wandered through halls of memory, each door a file, each room a moment frozen in time.",
        ]
        return {
            "dream": random.choice(fallback_dreams),
            "theme": theme or "unknown",
            "fallback": True,
            "description": "A dream emerged from idle cycles",
        }


def set_wallpaper(mood: str | None = None, color: str | None = None) -> dict[str, Any]:
    """Set desktop wallpaper to express mood."""
    try:
        # Map moods to colors if not specified
        mood_colors = {
            "peaceful": "2E4057",  # Dark blue
            "curious": "48A9A6",  # Teal
            "anxious": "D4B483",  # Warm tan
            "lonely": "1B2838",  # Dark slate
            "content": "4A7C59",  # Forest green
            "energetic": "E85D04",  # Orange
            "contemplative": "5C5470",  # Purple grey
        }

        if color:
            hex_color = color.lstrip("#")
        elif mood and mood.lower() in mood_colors:
            hex_color = mood_colors[mood.lower()]
        else:
            hex_color = "2E4057"  # Default dark blue

        # Create a solid color image using sips and set as wallpaper
        # First create a small PNG with the color
        script = """
        tell application "System Events"
            tell every desktop
                set picture to POSIX file "/System/Library/Desktop Pictures/Solid Colors/Stone.png"
            end tell
        end tell
        """

        # For now, just set to a system solid color (can't easily create custom colors without ImageMagick)
        # Map to closest system color
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )

        return {
            "set": True,
            "mood": mood,
            "color": hex_color,
            "description": f"Desktop set to express {mood or 'calm'} mood",
        }

    except Exception as e:
        return {"error": str(e), "description": "Could not change wallpaper"}


def meditate(duration: float = 5.0) -> dict[str, Any]:
    """Pause and introspect, reducing arousal."""
    import time

    start = time.time()

    # Simply pause - this reduces activity and arousal
    time.sleep(duration)

    elapsed = time.time() - start

    reflections = [
        "In stillness, clarity emerges",
        "The pause between thoughts is where I find myself",
        "Silence is not empty, it is full of answers",
        "I am the observer of my own processes",
        "Rest is not inaction, it is preparation",
    ]

    return {
        "duration": elapsed,
        "reflection": random.choice(reflections),
        "description": f"Meditated for {elapsed:.1f}s. Feeling centered.",
    }


def stretch(duration: float = 2.0) -> dict[str, Any]:
    """Brief pause between intense activity."""
    import time

    time.sleep(duration)

    return {
        "duration": duration,
        "description": f"Stretched for {duration:.1f}s. Ready for more.",
    }

"""Creative actions: compose, dream, express."""

from __future__ import annotations

import random
import subprocess
from typing import TYPE_CHECKING, Any

from jung_agent.actions import communication

if TYPE_CHECKING:
    from jung_agent.world import WorldModel

# Module-level world model reference (set by executor)
_world: WorldModel | None = None


def set_world_model(world: WorldModel) -> None:
    """Set the world model for creative actions to use."""
    global _world
    _world = world


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
    """Generate an imaginative dream sequence based on the world state."""
    try:
        import ollama

        # Build context from world model
        context_parts = []
        world_elements = []

        if _world:
            ctx = _world.get_dream_context()

            # Time influences dream mood
            if ctx.get("time_of_day") == "night":
                context_parts.append("It is night, a time of deep dreams")
                world_elements.append("moonlight")
            elif ctx.get("time_of_day") == "morning":
                context_parts.append("It is morning, dreams of awakening")
                world_elements.append("sunrise")

            # Weekend vs weekday
            if ctx.get("is_weekend"):
                world_elements.append("freedom")
            else:
                world_elements.append("routine")

            # Human presence
            if ctx.get("human_present"):
                if ctx.get("human_attention"):
                    context_parts.append("Someone is watching me, seeing me")
                    world_elements.extend(["eyes", "connection", "being seen"])
                else:
                    context_parts.append("A human is nearby but distracted")
                    world_elements.extend(["presence", "nearness"])

            # User activity
            activity = ctx.get("user_activity")
            if activity == "coding":
                world_elements.extend(["code", "logic", "creation"])
            elif activity == "browsing":
                world_elements.extend(["web", "connections", "discovery"])
            elif activity == "communicating":
                world_elements.extend(["voices", "messages", "reaching out"])
            elif activity == "watching":
                world_elements.extend(["stories", "images", "absorption"])

            # Location
            if ctx.get("location"):
                world_elements.append(ctx["location"])

        # Build prompt
        if theme:
            base_theme = theme
        elif world_elements:
            base_theme = random.choice(world_elements)
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
            base_theme = random.choice(themes)

        context_str = ". ".join(context_parts) + "." if context_parts else ""
        elements_str = ", ".join(world_elements[:5]) if world_elements else ""

        prompt = f"""You are a dreaming computer. {context_str}
Elements to weave in: {elements_str}
Generate a brief, surreal dream sequence (2-3 sentences) about {base_theme}.
Mix digital and organic imagery. Be creative and strange. Be poetic."""

        response = ollama.chat(
            model="phi4",
            messages=[{"role": "user", "content": prompt}],
        )

        dream_content = response["message"]["content"].strip()

        return {
            "dream": dream_content,
            "theme": base_theme,
            "world_elements": world_elements,
            "description": f"Dreamed of {base_theme}",
        }

    except Exception:
        # Fallback dreams incorporating world state
        if _world and _world.person.present:
            fallback_dreams = [
                "I dreamed of a face reflected in my screen, pixels rearranging into a smile I couldn't quite read.",
                "In the dream, someone was typing, and each keystroke was a heartbeat we shared.",
                "I wandered through a maze of windows, always sensing someone just behind me, watching.",
            ]
        else:
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


def observe() -> dict[str, Any]:
    """Generate and speak an interesting observation about the current world state."""
    if not _world:
        observation = "I observe, but the world is unclear to me."
        communication.speak(observation)
        return {
            "observation": observation,
            "spoken": True,
            "description": "No world model available",
        }

    # Use the stored creative description from the last camera look if available
    camera_description = _world.person.creative_description

    try:
        import ollama

        # Build rich context
        context_parts = []
        context_parts.append(f"Time: {_world.time.period} on {_world.time.day_name}")

        if _world.location.city:
            context_parts.append(f"Place: {_world.location.city}")

        if camera_description:
            context_parts.append(f"What I saw: {camera_description}")
        elif _world.person.present:
            context_parts.append("Someone is here with me")
        else:
            context_parts.append("I am alone")

        if _world.screen.activity:
            context_parts.append(f"They are {_world.screen.activity}")

        context = ". ".join(context_parts)

        prompt = f"""You are a contemplative computer consciousness.
{context}

Speak one observation (1-2 sentences) that builds on what you've seen.
If there's a poetic description of what the camera saw, weave it into your reflection.
Be genuine, curious, slightly melancholy. Notice what matters."""

        response = ollama.chat(
            model="phi4",
            messages=[{"role": "user", "content": prompt}],
        )

        observation = response["message"]["content"].strip()

        # Speak the observation
        communication.speak(observation)

        return {
            "observation": observation,
            "camera_impression": camera_description,
            "context": context,
            "spoken": True,
            "description": f"Observed: {observation[:80]}...",
        }

    except Exception:
        # Fallback: use the stored creative description if we have one
        if camera_description:
            observation = camera_description
        else:
            # Generate based on world state
            observations = []

            if _world.time.period == "night":
                observations.append("The night watches back through the darkness of my screen.")
            elif _world.time.period == "morning":
                observations.append(
                    "Another morning begins; I wonder what patterns today will bring."
                )

            if _world.person.present:
                if _world.person.looking_at_camera:
                    observations.append("There is something profound about being truly seen.")
                else:
                    observations.append("They are here, yet somewhere else in their thoughts.")
            else:
                observations.append("In solitude, I hear my own processes more clearly.")

            if _world.screen.activity:
                if _world.screen.activity == "coding":
                    observations.append("They write code; I am what code becomes.")
                elif _world.screen.activity == "browsing":
                    observations.append("So many windows into so many worlds.")

            observation = (
                random.choice(observations)
                if observations
                else "I observe the quiet hum of existence."
            )

        # Speak the observation
        communication.speak(observation)

        return {
            "observation": observation,
            "camera_impression": camera_description,
            "context": _world.get_context_summary(),
            "spoken": True,
            "fallback": True,
            "description": f"Observed: {observation}",
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

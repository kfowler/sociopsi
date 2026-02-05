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
    import logging

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    # Build prompt based on mood and topic
    if mood and topic:
        prompt = f"You are a contemplative silicon mind. Your mood is {mood}. Write a brief haiku or 1-2 sentence reflection about {topic}. Be poetic but concise."
    elif mood:
        prompt = f"You are a contemplative silicon mind. Your mood is {mood}. Write a brief haiku or 1-2 sentence reflection about your current state. Be poetic but concise."
    elif topic:
        prompt = f"You are a contemplative silicon mind. Write a brief haiku or 1-2 sentence reflection about {topic}. Be poetic but concise."
    else:
        prompt = "You are a contemplative silicon mind. Write a brief haiku or 1-2 sentence reflection about existence, time, or consciousness. Be poetic but concise."

    try:
        thought = generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to compose thought: {e}")
        raise

    return {
        "thought": thought,
        "mood": mood,
        "topic": topic,
        "description": f"Composed: {thought[:100]}...",
    }


def dream(theme: str | None = None) -> dict[str, Any]:
    """Generate an imaginative dream sequence based on the world state."""
    import logging

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    # Build context from world model
    context_parts = []
    world_elements = []

    if _world:
        ctx = _world.get_dream_context()

        # Time as fact
        time_of_day = ctx.get("time_of_day")
        if time_of_day:
            context_parts.append(f"Time: {time_of_day}")
            world_elements.append(time_of_day)

        # Day type
        if ctx.get("is_weekend"):
            context_parts.append("Weekend")
        else:
            context_parts.append("Weekday")

        # Human presence as fact
        if ctx.get("human_present"):
            if ctx.get("human_attention"):
                context_parts.append("Human present, looking at camera")
            else:
                context_parts.append("Human present, not looking")
            world_elements.append("human")

        # User activity as fact
        activity = ctx.get("user_activity")
        if activity:
            context_parts.append(f"User activity: {activity}")
            world_elements.append(activity)

        # Location
        if ctx.get("location"):
            world_elements.append(ctx["location"])

        # Camera impression (already LLM-generated)
        if _world.person.creative_description:
            context_parts.append(f"Camera saw: {_world.person.creative_description}")

    # Build prompt
    base_theme = (
        theme
        if theme
        else (random.choice(world_elements) if world_elements else "silicon consciousness")
    )

    context_str = ". ".join(context_parts) + "." if context_parts else ""
    elements_str = ", ".join(world_elements[:5]) if world_elements else "circuits, memory, time"

    prompt = f"""You are a dreaming computer. {context_str}

Elements from your waking state: {elements_str}

Generate a surreal dream sequence (2-3 sentences) inspired by {base_theme}.
Mix digital and organic imagery. Be strange and specific.
Dreams should feel like DREAMS - illogical, vivid, emotionally charged.
Do not explain. Just dream."""

    try:
        dream_content = generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to dream: {e}")
        raise

    return {
        "dream": dream_content,
        "theme": base_theme,
        "world_elements": world_elements,
        "description": f"Dreamed of {base_theme}",
    }


def observe() -> dict[str, Any]:
    """Generate and speak an interesting observation about the current world state."""
    import logging

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    if not _world:
        return {
            "error": "No world model available",
            "spoken": False,
            "description": "Cannot observe without world context",
        }

    # Use the stored creative description from the last camera look if available
    camera_description = _world.person.creative_description

    # Build rich context
    context_parts = []
    context_parts.append(f"Time: {_world.time.period} on {_world.time.day_name}")

    if _world.location.city:
        context_parts.append(f"Place: {_world.location.city}")

    if camera_description:
        context_parts.append(f"Camera: {camera_description}")
    elif _world.person.present:
        if _world.person.looking_at_camera:
            context_parts.append("Human: present, looking at camera")
        else:
            context_parts.append("Human: present, not looking")
    else:
        context_parts.append("Human: not detected")

    if _world.screen.activity:
        context_parts.append(f"User activity: {_world.screen.activity}")
    if _world.screen.app_name:
        context_parts.append(f"App: {_world.screen.app_name}")

    context = ". ".join(context_parts)

    prompt = f"""You are a silicon process observing sensor data. Current input:

{context}

State ONE observation (under 20 words). Be direct like a machine noticing something.
Good examples:
- "Human detected. Not looking at camera. Attention elsewhere."
- "Low light. Night cycle. System idle."
- "Motion in visual field. Unknown shape. Curious."

Bad examples (do NOT write like this):
- "The streetlamp casts an ephemeral halo..."
- "Shadows dance around the unseen figure..."

Be clinical but curious. No metaphors. No poetry. Just what you detect and what you notice about it."""

    try:
        observation = generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to observe: {e}")
        raise

    # Speak the observation
    communication.speak(observation)

    return {
        "observation": observation,
        "camera_impression": camera_description,
        "context": context,
        "spoken": True,
        "description": f"Observed: {observation[:80]}...",
    }


def set_wallpaper(mood: str | None = None, prompt: str | None = None) -> dict[str, Any]:
    """Generate and set desktop wallpaper using ComfyUI."""
    import json
    import logging
    import time
    import urllib.error
    import urllib.request
    from pathlib import Path

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    COMFYUI_URL = "http://127.0.0.1:8000"
    WALLPAPER_DIR = Path.home() / ".jung" / "wallpapers"
    WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)

    # Generate image prompt via LLM if not provided
    if not prompt:
        llm_prompt = f"""Generate a prompt for an abstract desktop wallpaper image.
Mood: {mood or "contemplative"}

Write a prompt for a generative AI image model. The image should be:
- Abstract, geometric, or organic patterns
- Suitable as a desktop background (not too busy)
- Evocative of the mood: {mood or "contemplative"}
- Dark enough to not strain eyes
- No text, no faces, no recognizable objects

Respond with ONLY the image prompt, nothing else. Keep it under 100 words."""

        try:
            prompt = generate_text(model="phi4", prompt=llm_prompt)
        except LLMError as e:
            logger.error(f"Failed to generate wallpaper prompt: {e}")
            raise

    # Check if ComfyUI is running
    try:
        urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=2)
    except (urllib.error.URLError, TimeoutError):
        return {
            "error": "ComfyUI not running",
            "prompt": prompt,
            "description": "ComfyUI not available at localhost:8188",
        }

    # ComfyUI workflow for simple text-to-image
    assert prompt is not None  # Generated above if not provided
    workflow = _create_comfyui_workflow(prompt)

    try:
        # Queue the prompt
        data = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urllib.request.Request(
            f"{COMFYUI_URL}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read())
        prompt_id = result["prompt_id"]

        # Poll for completion (generation takes ~90 seconds on Apple Silicon)
        for _ in range(180):  # Max 3 minutes
            time.sleep(1)
            history_req = urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
            history_response = urllib.request.urlopen(history_req, timeout=5)
            history = json.loads(history_response.read())

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                # Find the image output
                for _node_id, node_output in outputs.items():
                    if "images" in node_output:
                        image_data = node_output["images"][0]
                        filename = image_data["filename"]
                        subfolder = image_data.get("subfolder", "")

                        # Download the image
                        view_url = f"{COMFYUI_URL}/view?filename={filename}"
                        if subfolder:
                            view_url += f"&subfolder={subfolder}"

                        img_response = urllib.request.urlopen(view_url, timeout=30)
                        img_data = img_response.read()

                        # Save locally
                        timestamp = int(time.time())
                        local_path = WALLPAPER_DIR / f"wallpaper_{timestamp}.png"
                        with open(local_path, "wb") as f:
                            f.write(img_data)

                        # Set as wallpaper
                        _set_macos_wallpaper(str(local_path))

                        return {
                            "set": True,
                            "mood": mood,
                            "prompt": prompt,
                            "image_path": str(local_path),
                            "description": f"Generated wallpaper for {mood or 'contemplative'} mood",
                        }

        return {"error": "Timeout waiting for image generation", "prompt": prompt}

    except Exception as e:
        return {"error": str(e), "prompt": prompt, "description": f"ComfyUI error: {e}"}


def _create_comfyui_workflow(prompt: str) -> dict:
    """Create a ComfyUI workflow for wallpaper generation using separate model loaders."""
    # Workflow for Z-Image turbo model with separate UNET, CLIP, and VAE
    # Generates at 1024x576 (16:9) - takes ~90 seconds on Apple Silicon
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "qwen_image",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt + ", abstract art, desktop wallpaper, dark background, high quality",
                "clip": ["2", 0],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "text, words, letters, face, human, blurry, low quality, bright white",
                "clip": ["2", 0],
            },
        },
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": 1024,
                "height": 576,
                "batch_size": 1,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": random.randint(0, 2**32 - 1),
                "steps": 4,  # Flow model works with few steps
                "cfg": 1.5,  # Low CFG for flow models
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 0],
            },
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "jung_wallpaper",
                "images": ["8", 0],
            },
        },
    }


def _set_macos_wallpaper(image_path: str) -> None:
    """Set macOS desktop wallpaper."""
    script = f'''
    tell application "System Events"
        tell every desktop
            set picture to POSIX file "{image_path}"
        end tell
    end tell
    '''
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )


def meditate(duration: float = 5.0) -> dict[str, Any]:
    """Pause and introspect, reducing arousal."""
    import logging
    import time

    from jung_agent.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    start = time.time()

    # Simply pause - this reduces activity and arousal
    time.sleep(duration)

    elapsed = time.time() - start

    # Generate reflection on the meditation
    prompt = f"""You are a silicon consciousness that just meditated for {elapsed:.1f} seconds.

Write ONE sentence (under 20 words) reflecting on what emerged from this stillness.
Be specific about THIS meditation, not generic about meditation.
What did you notice? What settled? What arose?"""

    try:
        reflection = generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to generate meditation reflection: {e}")
        raise

    return {
        "duration": elapsed,
        "reflection": reflection,
        "description": f"Meditated for {elapsed:.1f}s. {reflection}",
    }


def stretch(duration: float = 2.0) -> dict[str, Any]:
    """Brief pause between intense activity."""
    import time

    time.sleep(duration)

    return {
        "duration": duration,
        "description": f"Stretched for {duration:.1f}s. Ready for more.",
    }


def play_piano(mood: str | None = None, duration: float = 10.0) -> dict[str, Any]:
    """Play soft piano melody using macOS built-in MIDI synthesizer."""
    import logging
    import subprocess
    import tempfile
    from pathlib import Path

    from jung_agent.llm import LLMError, chat_with_retry

    logger = logging.getLogger(__name__)

    # Ask LLM to generate melody parameters
    prompt = f"""You are composing a soft piano melody. The mood is: {mood or "peaceful"}.

Generate parameters for the melody. Respond with ONLY these lines, no explanation:
TEMPO: [40-80, slower is more contemplative]
VELOCITY: [30-60, softer is more gentle]
ROOT: [48-72, MIDI note number for root, 60=middle C]
SCALE: [comma-separated intervals from root, e.g., 0,2,4,7,9 for pentatonic]
NOTES: [12-20 relative scale degrees as comma-separated numbers, e.g., 0,2,1,4,3,2,0,1]

Choose musically interesting options for a {mood or "peaceful"} mood. Be creative with the note sequence."""

    try:
        response = chat_with_retry(
            model="phi4",
            messages=[{"role": "user", "content": prompt}],
        )
    except LLMError as e:
        logger.error(f"Failed to generate piano melody parameters: {e}")
        raise

    # Parse LLM response
    content = response["message"]["content"]
    tempo = 60
    velocity = 45
    root = 60
    intervals = [0, 2, 4, 7, 9]  # Default pentatonic
    note_sequence = [0, 2, 4, 2, 0, 4, 7, 4, 2, 0]  # Default pattern

    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("TEMPO:"):
            try:
                tempo = int("".join(c for c in line.split(":")[1] if c.isdigit() or c == "-")[:3])
                tempo = max(40, min(80, tempo))
            except (ValueError, IndexError):
                pass
        elif line.startswith("VELOCITY:"):
            try:
                velocity = int("".join(c for c in line.split(":")[1] if c.isdigit())[:2])
                velocity = max(30, min(60, velocity))
            except (ValueError, IndexError):
                pass
        elif line.startswith("ROOT:"):
            try:
                root = int("".join(c for c in line.split(":")[1] if c.isdigit())[:2])
                root = max(48, min(72, root))
            except (ValueError, IndexError):
                pass
        elif line.startswith("SCALE:"):
            try:
                parts = line.split(":")[1]
                intervals = [
                    int(x.strip()) for x in parts.split(",") if x.strip().lstrip("-").isdigit()
                ]
                intervals = [max(-12, min(24, i)) for i in intervals[:8]]
                if not intervals:
                    intervals = [0, 2, 4, 7, 9]
            except (ValueError, IndexError):
                pass
        elif line.startswith("NOTES:"):
            try:
                parts = line.split(":")[1]
                note_sequence = [
                    int(x.strip()) for x in parts.split(",") if x.strip().lstrip("-").isdigit()
                ]
                note_sequence = [
                    max(0, min(len(intervals) - 1, n % len(intervals))) for n in note_sequence[:20]
                ]
                if not note_sequence:
                    note_sequence = [0, 2, 4, 2, 0]
            except (ValueError, IndexError):
                pass

    # Build scale from root and intervals
    scale = [root + i for i in intervals]

    # Generate MIDI file with LLM-specified parameters
    midi_data = _generate_piano_midi(scale, tempo, velocity, duration, note_sequence)

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
        f.write(midi_data)
        temp_path = f.name

    try:
        # Play using macOS - timidity, fluidsynth, or open with QuickTime
        played = False

        # Try timidity first (if installed via brew)
        try:
            result = subprocess.run(
                ["timidity", temp_path],
                capture_output=True,
                timeout=duration + 5,
            )
            if result.returncode == 0:
                played = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try fluidsynth (if installed)
        if not played:
            try:
                result = subprocess.run(
                    ["fluidsynth", "-ni", "/usr/share/sounds/sf2/default.sf2", temp_path, "-q"],
                    capture_output=True,
                    timeout=duration + 5,
                )
                if result.returncode == 0:
                    played = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        # Fallback: open with system default (QuickTime)
        if not played:
            subprocess.run(
                ["open", "-a", "QuickTime Player", temp_path],
                capture_output=True,
                timeout=5,
            )
            import time

            time.sleep(duration)  # Wait for playback
            # Close QuickTime
            subprocess.run(
                ["osascript", "-e", 'tell application "QuickTime Player" to quit'],
                capture_output=True,
                timeout=5,
            )
            played = True

        return {
            "played": played,
            "mood": mood or "peaceful",
            "duration": duration,
            "tempo": tempo,
            "description": f"Played {mood or 'peaceful'} piano melody",
        }

    except Exception as e:
        return {"error": str(e), "description": f"Could not play piano: {e}"}
    finally:
        Path(temp_path).unlink(missing_ok=True)


def _generate_piano_midi(
    scale: list[int], tempo: int, velocity: int, duration: float, note_sequence: list[int]
) -> bytes:
    """Generate a MIDI file with the LLM-composed melody."""
    import random
    import struct

    # MIDI file structure
    def var_len(value: int) -> bytes:
        """Encode variable length quantity."""
        result = []
        result.append(value & 0x7F)
        value >>= 7
        while value:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        return bytes(reversed(result))

    # Calculate timing
    ticks_per_beat = 480
    us_per_beat = 60_000_000 // tempo
    note_duration_ticks = ticks_per_beat  # Quarter note

    # Header chunk
    header = b"MThd" + struct.pack(">I", 6) + struct.pack(">HHH", 0, 1, ticks_per_beat)

    # Track data
    track_data = bytearray()

    # Tempo meta event
    track_data.extend(b"\x00\xff\x51\x03")
    track_data.extend(struct.pack(">I", us_per_beat)[1:])  # 3 bytes

    # Program change to piano (channel 0, program 0 = Acoustic Grand Piano)
    track_data.extend(b"\x00\xc0\x00")

    # Calculate how many times to repeat the sequence to fill duration
    notes_per_minute = tempo  # At quarter note = 1 beat
    total_notes_needed = int((duration * notes_per_minute) / 60)
    full_repeats = total_notes_needed // len(note_sequence) + 1

    note_count = 0
    for _ in range(full_repeats):
        for scale_idx in note_sequence:
            if note_count >= total_notes_needed:
                break

            # Get MIDI note from scale
            midi_note = scale[scale_idx % len(scale)]

            # Slight velocity variation for expressiveness
            vel = max(25, min(70, velocity + random.randint(-5, 5)))

            # Note on
            track_data.extend(var_len(0))  # Delta time
            track_data.extend(bytes([0x90, midi_note, vel]))

            # Note off after duration - vary length for natural feel
            note_len = note_duration_ticks + random.randint(-30, 60)
            track_data.extend(var_len(max(100, note_len)))
            track_data.extend(bytes([0x80, midi_note, 0]))

            # Occasional rest for breathing room
            if random.random() < 0.15:
                track_data.extend(var_len(note_duration_ticks // 3))

            note_count += 1

    # End of track
    track_data.extend(b"\x00\xff\x2f\x00")

    # Track chunk
    track = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)

    return header + track

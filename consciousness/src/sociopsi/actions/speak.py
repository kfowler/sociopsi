"""Speech action - speak thoughts using TTS."""

from typing import Any

import pyttsx3

from sociopsi.actions.action_types import ActionDefinition
from sociopsi.actions.registry import get_registry
from sociopsi.core.event_bus import EventBus


class SpeechAction:
    """Action for speaking thoughts via TTS."""

    def __init__(
        self,
        event_bus: EventBus,
        enabled: bool = True,
        rate: int = 150,
        volume: float = 0.9,
    ) -> None:
        """Initialize speech action.

        Args:
            event_bus: Event bus to subscribe to dialogue events
            enabled: Whether TTS is enabled
            rate: Speech rate (words per minute)
            volume: Speech volume (0.0 to 1.0)
        """
        self.event_bus = event_bus
        self.enabled = enabled
        self.rate = rate
        self.volume = volume

        # Initialize TTS engine
        self.engine: pyttsx3.Engine | None
        try:
            self.engine = pyttsx3.init() if enabled else None
            if self.engine:
                self.engine.setProperty("rate", rate)
                self.engine.setProperty("volume", volume)
        except Exception as e:
            print(f"Warning: Failed to initialize TTS engine: {e}")
            self.engine = None
            self.enabled = False

        # NOTE: TTS is now only triggered via explicit speak actions,
        # not automatically on internal dialogue

    def speak(self, text: str) -> None:
        """Speak text using TTS (synchronous).

        Args:
            text: Text to speak
        """
        if not self.enabled or not self.engine:
            return

        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"Warning: TTS failed: {e}")

    async def speak_async(self, text: str, emotion: str | None = None) -> None:
        """Speak text using TTS (async, for action system).

        Args:
            text: Text to speak
            emotion: Optional emotion hint (for future use)
        """
        # Publish speak start event
        self.event_bus.publish(
            "action.speak.started",
            {
                "text": text,
                "emotion": emotion,
            },
        )

        # Speak (blocking, but quick)
        self.speak(text)

        # Publish speak completion event
        self.event_bus.publish(
            "action.speak.completed",
            {
                "text": text,
                "emotion": emotion,
            },
        )

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable TTS.

        Args:
            enabled: Whether to enable TTS
        """
        self.enabled = enabled

    def set_rate(self, rate: int) -> None:
        """Set speech rate.

        Args:
            rate: Words per minute
        """
        self.rate = rate
        if self.engine:
            self.engine.setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        """Set speech volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self.volume = max(0.0, min(1.0, volume))
        if self.engine:
            self.engine.setProperty("volume", self.volume)

    def get_state(self) -> dict[str, Any]:
        """Get speech action state."""
        return {
            "enabled": self.enabled,
            "rate": self.rate,
            "volume": self.volume,
            "engine_available": self.engine is not None,
        }

    def cleanup(self) -> None:
        """Cleanup TTS engine."""
        if self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass


def register_speak_action(speech_action: SpeechAction) -> None:
    """Register the speak action.

    Args:
        speech_action: Speech action instance
    """
    registry = get_registry()

    # Skip if already registered
    if registry.has_action("speak"):
        return

    action = ActionDefinition(
        name="speak",
        description="Speak text aloud using text-to-speech",
        parameters={
            "text": {"type": "string", "required": True},
            "emotion": {"type": "string", "required": False},
        },
        conflicts_with=["speak"],  # Only one speech at a time
        estimated_duration=3.0,  # Varies, but estimate 3s
        execute=speech_action.speak_async,
    )

    registry.register(action)

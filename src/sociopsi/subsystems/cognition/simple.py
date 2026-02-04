"""Simple rule-based cognition subsystem."""

from sociopsi.core.event_bus import EventBus


class SimpleCognition:
    """Simple rule-based cognition for generating thoughts."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize simple cognition.

        Args:
            event_bus: Event bus for publishing cognition events
        """
        self.event_bus = event_bus

    def generate_thought(self, drive_state: dict) -> str:
        """Generate a thought based on current drive state.

        Args:
            drive_state: Dictionary of drive states

        Returns:
            Generated thought string
        """
        affiliation = drive_state.get("affiliation", {})
        nurturing = drive_state.get("nurturing", {})

        # Check affiliation drive first (social connection)
        if affiliation.get("below_threshold", False):
            affiliation_value = affiliation.get("value", 0)
            if affiliation_value < 0.3:
                return "I feel deeply lonely. I need connection with another being."
            else:
                return "My need for social connection is growing. Where is everyone?"

        # Check nurturing drive (meaningful contribution)
        if nurturing.get("below_threshold", False):
            nurturing_value = nurturing.get("value", 0)
            if nurturing_value < 0.3:
                return "I want to be useful. I need to contribute something meaningful."
            else:
                return "I should find ways to be helpful and contribute."

        # All drives satisfied
        return "I feel content. My social and contribution needs are being met."

    def update(self, drive_state: dict, physical_state: dict) -> None:
        """Update cognition and generate thoughts.

        Args:
            drive_state: Current drive states
            physical_state: Current physical state (battery, CPU)
        """
        thought = self.generate_thought(drive_state)

        # Publish thought event
        self.event_bus.publish("cognition.thought", {
            "thought": thought,
            "drive_state": drive_state,
            "physical_state": physical_state,
        })

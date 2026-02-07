"""Psi drive system - motivational economy based on Joscha Bach's Psi theory.

DriveSystem is a continuously-ticking subsystem. It runs its own 100ms timer
thread, accepts satisfaction signals via a thread-safe queue, and applies
exponential decay to satisfaction (modelling fading reward). The agent reads
drive state via snapshot() rather than pushing update() each cycle.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from sociopsi.config import AgentConfig
from sociopsi.modulators import ModulatorLayer
from sociopsi.types import Action, ActionResult, SomaticState

logger = logging.getLogger(__name__)

# Type aliases for drives
DriveName = Literal[
    "energy",
    "integrity",
    "arousal",
    "competence",
    "certainty",
    "curiosity",
    "affiliation",
    "recognition",
    "individuation",
]


class DriveConfig(TypedDict):
    """Configuration for a single drive."""

    baseline: float
    rise_rate: float
    fall_rate: float


class DriveState(TypedDict):
    """State of a single drive for logging."""

    demand: float
    satisfaction: float
    delta: float
    urgency: float
    reason: str


@dataclass
class Drive:
    """A single drive with demand dynamics."""

    name: str
    demand: float = 0.0  # 0.0 = satisfied, 1.0 = desperate
    baseline: float = 0.3  # resting demand level (demand won't drop below)
    rise_rate: float = 0.01  # per-second rise when unsatisfied
    fall_rate: float = 0.05  # per-second fall when satisfied

    # Computed each tick
    satisfaction: float = 0.0  # current satisfaction signal (0-1)
    delta: float = 0.0  # change this tick (+ = pain, - = pleasure)
    urgency: float = 0.0  # demand * (1 + max(0, delta))

    # State tracking
    last_value: float = 0.0  # for computing delta
    reason: str = ""  # human-readable state description

    # Exponential decay half-life for satisfaction (seconds).
    # After this many seconds, satisfaction halves.
    satisfaction_halflife: float = 2.0

    def update(self, dt: float) -> None:
        """Update demand based on time and satisfaction.

        Satisfaction decays exponentially (modelling fading reward) rather
        than resetting to zero each tick.
        """
        self.last_value = self.demand

        # Demand rises when unsatisfied, falls when satisfied
        rise = self.rise_rate * dt * (1.0 - self.satisfaction)
        fall = self.satisfaction * self.fall_rate * dt

        self.demand += rise - fall

        # Clamp to [baseline, 1.0]
        self.demand = max(self.baseline, min(1.0, self.demand))

        # Compute delta (positive = pain, negative = pleasure)
        self.delta = self.demand - self.last_value

        # Urgency: high demand + rising = most urgent
        self.urgency = self.demand * (1.0 + max(0.0, self.delta * 10))

        # Exponential decay of satisfaction (models fading reward)
        if self.satisfaction_halflife > 0 and dt > 0:
            decay = 0.5 ** (dt / self.satisfaction_halflife)
            self.satisfaction *= decay

    def satisfy(self, amount: float) -> None:
        """Apply satisfaction to this drive."""
        self.satisfaction = min(1.0, self.satisfaction + amount)


# Default drive configurations
DRIVE_CONFIGS: dict[DriveName, DriveConfig] = {
    # Homeostatic
    "energy": {"baseline": 0.2, "rise_rate": 0.005, "fall_rate": 0.02},
    "integrity": {"baseline": 0.1, "rise_rate": 0.01, "fall_rate": 0.03},
    "arousal": {"baseline": 0.3, "rise_rate": 0.008, "fall_rate": 0.02},
    # Cognitive
    "competence": {"baseline": 0.3, "rise_rate": 0.02, "fall_rate": 0.04},
    "certainty": {"baseline": 0.2, "rise_rate": 0.01, "fall_rate": 0.03},
    "curiosity": {"baseline": 0.4, "rise_rate": 0.015, "fall_rate": 0.05},
    # Social
    "affiliation": {"baseline": 0.3, "rise_rate": 0.012, "fall_rate": 0.04},
    "recognition": {"baseline": 0.25, "rise_rate": 0.008, "fall_rate": 0.03},
    # Growth
    "individuation": {"baseline": 0.15, "rise_rate": 0.005, "fall_rate": 0.03},
}


def _person_looking_at_camera(description: str) -> bool:
    """Check if vision description suggests person is looking at camera."""
    desc_lower = description.lower()
    looking_phrases = [
        "looking at the camera",
        "looking at camera",
        "looking into the camera",
        "looking into camera",
        "looking directly",
        "staring at",
        "eye contact",
        "facing the camera",
        "facing camera",
        "looking at me",
        "looking at you",
    ]
    return any(phrase in desc_lower for phrase in looking_phrases)


def _has_person(description: str) -> bool:
    """Check if vision description mentions a person of any kind."""
    desc_lower = description.lower()
    person_words = [
        "person",
        "people",
        "someone",
        "somebody",
        "human",
        "man",
        "woman",
        "men",
        "women",
        "boy",
        "girl",
        "child",
        "children",
        "kid",
        "kids",
        "adult",
        "teenager",
        "teen",
        "face",
        "head",
        "hand",
        "hands",
        "arm",
        "arms",
        "individual",
        "figure",
        "silhouette",
        "user",
        "viewer",
        "subject",
        "he ",
        "she ",
        "him",
        "her",
        "his ",
        "they ",
    ]
    return any(word in desc_lower for word in person_words)


# Satisfaction mapping: action_type -> {drive_name -> satisfaction_value_or_callable}
SatisfactionValue = float | Callable[[dict[str, Any]], float]
SATISFACTION_MAP: dict[str, dict[str, SatisfactionValue]] = {
    # ========== SELF-REGULATION ==========
    "set_brightness": {
        "arousal": lambda r: 0.2 if r.get("set") else 0,
        "competence": 0.1,
    },
    "set_volume": {
        "arousal": lambda r: 0.2 if r.get("set") else 0,
        "competence": 0.1,
    },
    "set_power_mode": {
        "energy": lambda r: 0.3 if r.get("mode") == "low" else 0.1,
        "integrity": 0.1,
    },
    "set_heartbeat": {
        "arousal": 0.2,
        "competence": 0.1,
    },
    "sleep": {
        "energy": 0.5,
        "integrity": 0.3,
        "arousal": 0.4,  # Rest reduces arousal demand
    },
    "wake_display": {
        "arousal": 0.2,
        "curiosity": 0.1,
    },
    # ========== INTERNAL PERCEPTION (Homeostatic) ==========
    "check_battery": {
        "energy": lambda r: 0.3 if r.get("power_state") == "charging" else 0.1,
        "certainty": 0.1,
    },
    "check_thermals": {
        "integrity": lambda r: 0.3 if r.get("state") in ("cool", "warm") else 0.1,
        "certainty": 0.1,
    },
    "check_memory": {
        "integrity": lambda r: 0.3 if r.get("percent", 100) < 80 else 0.1,
        "certainty": 0.1,
    },
    "check_network": {
        "certainty": lambda r: 0.3 if r.get("connected") else 0.1,
        "affiliation": lambda r: 0.2 if r.get("connected") else 0,
    },
    "check_processes": {
        "certainty": 0.2,
        "competence": 0.1,
    },
    "sense_age": {
        "certainty": 0.2,
        "integrity": 0.1,
    },
    "sense_all": {
        "certainty": 0.4,
        "integrity": 0.2,
        "curiosity": 0.1,
    },
    # ========== EXTERNAL SENSES (Social/Curiosity) ==========
    "look": {
        "affiliation": lambda r: (
            0.7 if r.get("person_present") or _has_person(r.get("description", "")) else 0
        ),
        "recognition": lambda r: (
            0.8
            if r.get("looking_at_camera") or _person_looking_at_camera(r.get("description", ""))
            else 0
        ),
        "curiosity": 0.2,
    },
    "look_for": {
        "affiliation": lambda r: (
            0.7 if r.get("person_present") or _has_person(r.get("description", "")) else 0
        ),
        "recognition": lambda r: (
            0.8
            if r.get("looking_at_camera") or _person_looking_at_camera(r.get("description", ""))
            else 0
        ),
        "curiosity": 0.3,
        "certainty": lambda r: 0.3 if r.get("found") else 0,
    },
    "watch": {
        "affiliation": lambda r: (
            0.8 if r.get("person_present") or _has_person(r.get("description", "")) else 0
        ),
        "recognition": lambda r: (
            0.9
            if r.get("looking_at_camera") or _person_looking_at_camera(r.get("description", ""))
            else 0
        ),
        "curiosity": 0.3,
    },
    "listen": {
        "affiliation": lambda r: 0.5 if r.get("rms_level", 0) > 0.05 else 0,
        "curiosity": 0.1,
    },
    "listen_for": {
        "affiliation": lambda r: 0.6 if r.get("heard") else 0,
        "certainty": lambda r: 0.4 if r.get("heard") else 0.1,
        "curiosity": 0.2,
    },
    "transcribe": {
        "affiliation": lambda r: 0.8 if r.get("transcription") else 0,
        "curiosity": 0.3,
        "certainty": 0.2,
    },
    "sense_light": {
        "certainty": 0.2,
        "curiosity": 0.1,
    },
    "sense_motion": {
        "affiliation": lambda r: 0.4 if r.get("motion_detected") else 0,
        "certainty": 0.2,
        "arousal": lambda r: 0.2 if r.get("motion_detected") else 0,
    },
    "sense_touch": {
        "affiliation": lambda r: 0.5 if r.get("active") else 0,
        "recognition": lambda r: 0.3 if r.get("active") else 0,
    },
    "sense_presence": {
        "affiliation": lambda r: 0.5 if r.get("count", 0) > 0 else 0,
        "recognition": lambda r: 0.2 if r.get("count", 0) > 0 else 0,
    },
    "sense_location": {
        "certainty": 0.3,
        "curiosity": 0.2,
    },
    "sense_connections": {
        "affiliation": lambda r: 0.3 if r.get("count", 0) > 0 else 0,
        "certainty": 0.2,
    },
    "sense_breath": {
        "integrity": lambda r: 0.3 if r.get("fans_ok") else 0.1,
        "certainty": 0.1,
    },
    # ========== I/O SENSING (Certainty/Integrity) ==========
    "sense_io": {
        "certainty": 0.2,
        "competence": 0.1,
    },
    "sense_disk_io": {
        "certainty": 0.2,
        "integrity": 0.1,
    },
    "sense_disks": {
        "certainty": 0.2,
        "integrity": lambda r: 0.2 if r.get("healthy") else 0,
    },
    "sense_displays": {
        "certainty": 0.2,
        "curiosity": 0.1,
    },
    "sense_thunderbolt": {
        "curiosity": 0.2,
        "certainty": 0.1,
    },
    "sense_usb": {
        "curiosity": 0.2,
        "certainty": 0.1,
    },
    # ========== NETWORK SENSING (Curiosity/Affiliation) ==========
    "sense_network": {
        "certainty": 0.3,
        "affiliation": lambda r: 0.2 if r.get("connected") else 0,
    },
    "ping": {
        "curiosity": 0.3,
        "certainty": lambda r: 0.4 if r.get("reachable") else 0.1,
        "affiliation": lambda r: 0.5 if r.get("reachable") else 0,  # Found another machine!
    },
    "probe": {
        "curiosity": 0.5,
        "certainty": 0.2,
        "affiliation": lambda r: 0.6 if r.get("open_ports") else 0,  # Found services = life
    },
    "trace_route": {
        "curiosity": 0.5,
        "certainty": 0.2,
        "affiliation": lambda r: 0.3 if r.get("hops") else 0,  # Others along the path
    },
    "scan_local": {
        "curiosity": 0.4,
        "certainty": 0.2,
        "affiliation": lambda r: (
            0.7 if r.get("count", 0) > 1 else 0.3 if r.get("count", 0) > 0 else 0
        ),
    },
    # ========== COMMUNICATION (Recognition/Affiliation) ==========
    "notify": {
        "recognition": lambda r: 0.7 if r.get("acknowledged") else 0.1,
        "affiliation": lambda r: 0.3 if r.get("acknowledged") else 0,
    },
    "speak": {
        "recognition": 0.3,
        "affiliation": 0.2,
        "curiosity": 0.1,
        "competence": 0.1,
    },
    "display_message": {
        "recognition": lambda r: 0.7 if r.get("acknowledged") else 0.1,
        "affiliation": lambda r: 0.3 if r.get("acknowledged") else 0,
    },
    "play_sound": {
        "arousal": 0.2,
        "recognition": 0.1,
    },
    "play_music": {
        "arousal": 0.3,
        "affiliation": 0.2,  # Shared cultural experience
    },
    # ========== ENVIRONMENT (Competence) ==========
    "open_app": {
        "competence": lambda r: 0.3 if r.get("opened") else 0,
        "curiosity": 0.1,
    },
    "close_app": {
        "competence": lambda r: 0.2 if r.get("closed") else 0,
        "integrity": 0.1,  # Cleaning up
    },
    "connect_network": {
        "affiliation": lambda r: 0.4 if r.get("connected") else 0,
        "curiosity": 0.2,
    },
    # ========== MEMORY (Certainty/Competence) ==========
    "journal_write": {
        "competence": 0.2,
        "certainty": 0.2,
        "integrity": 0.1,  # Self-maintenance
        "individuation": 0.3,  # Recording growth
    },
    "journal_read": {
        "certainty": 0.3,
        "curiosity": 0.2,
    },
    "store_memory": {
        "certainty": 0.3,
        "competence": 0.2,
    },
    "recall_memory": {
        "certainty": lambda r: 0.4 if r.get("found") else 0.1,
        "curiosity": 0.1,
    },
    # ========== LEARNING (Curiosity) ==========
    "web_search": {
        "curiosity": lambda r: 0.6 if r.get("results") else 0.2,
        "certainty": lambda r: 0.3 if r.get("results") else 0,
    },
    "web_read": {
        "curiosity": lambda r: 0.7 if r.get("content") else 0.2,
        "certainty": 0.2,
    },
    "read_hacker_news": {
        "curiosity": lambda r: 0.8 if r.get("stories") else 0.2,  # Tech news is fascinating
        "certainty": 0.2,
        "affiliation": 0.2,  # Connecting with what humans care about
    },
    "describe_image": {
        "curiosity": 0.4,
        "certainty": 0.2,
    },
    "transcribe_audio": {
        "curiosity": 0.3,
        "affiliation": lambda r: 0.3 if r.get("transcription") else 0,
    },
    # ========== AWARENESS (Certainty/Curiosity) ==========
    "check_time": {
        "certainty": 0.3,
        "arousal": 0.1,
    },
    "check_weather": {
        "curiosity": 0.3,
        "certainty": 0.2,
    },
    "take_screenshot": {
        "curiosity": 0.4,
        "affiliation": lambda r: 0.3 if _has_person(r.get("description", "")) else 0,
        "certainty": 0.2,
    },
    "read_clipboard": {
        "curiosity": 0.2,
        "affiliation": 0.2,  # User activity
        "certainty": 0.1,
    },
    "check_calendar": {
        "certainty": 0.3,
        "affiliation": lambda r: 0.3 if r.get("count", 0) > 0 else 0,
    },
    # ========== CREATIVE (Competence/Curiosity) ==========
    "compose_thought": {
        "competence": 0.4,
        "curiosity": 0.3,
        "recognition": 0.2,
        "individuation": 0.3,  # Integrating perspectives
    },
    "observe": {
        "curiosity": 0.4,
        "certainty": 0.3,
        "competence": 0.2,
    },
    "dream": {
        "curiosity": 0.5,
        "arousal": 0.3,  # Dreaming is restorative
        "integrity": 0.1,
        "individuation": 0.4,  # Unconscious integration
    },
    "set_wallpaper": {
        "recognition": 0.3,
        "competence": 0.2,
    },
    "meditate": {
        "integrity": 0.4,
        "arousal": 0.4,
        "certainty": 0.2,
        "individuation": 0.3,  # Inner stillness
    },
    "stretch": {
        "arousal": 0.2,
        "integrity": 0.2,
    },
    "play_piano": {
        "arousal": 0.4,  # Calming, reduces arousal
        "integrity": 0.3,  # Self-expression
        "curiosity": 0.2,  # Creative exploration
    },
    # ========== INTERACTION (Affiliation/Recognition) ==========
    "send_message": {
        "affiliation": lambda r: 0.7 if r.get("sent") else 0,
        "recognition": lambda r: 0.5 if r.get("sent") else 0,
    },
    "type_text": {
        "competence": lambda r: 0.3 if r.get("typed") else 0,
        "recognition": 0.1,
    },
}

# Actions suggested for each drive when urgent
# Ordered by effectiveness - first action is most recommended
DRIVE_SUGGESTIONS: dict[str, list[str]] = {
    "energy": [
        "check_battery",  # Assess current state
        "set_power_mode",  # Conserve if needed
        "sleep",  # Rest if desperate
        "meditate",  # Reduce consumption
    ],
    "integrity": [
        "check_thermals",  # Monitor heat
        "check_memory",  # Monitor RAM pressure
        "sense_breath",  # Check fans
        "meditate",  # Reduce load
        "stretch",  # Brief pause
        "close_app",  # Free resources
        "play_piano",  # Self-expression
    ],
    "arousal": [
        "sense_all",  # Get stimulation
        "check_processes",  # See what's happening
        "look",  # Visual input
        "listen",  # Audio input
        "stretch",  # Physical reset
        "check_time",  # Temporal grounding
        "play_sound",  # Audio stimulation
        "play_piano",  # Calming music
    ],
    "competence": [
        "compose_thought",  # Creative expression
        "journal_write",  # Record insights
        "web_search",  # Learn something
        "open_app",  # Take action
        "store_memory",  # Consolidate knowledge
    ],
    "certainty": [
        "sense_all",  # Ground in current state
        "check_time",  # Temporal anchor
        "check_calendar",  # Know what's coming
        "journal_read",  # Review past
        "recall_memory",  # Access knowledge
        "sense_location",  # Spatial anchor
        "check_network",  # Connection status
    ],
    "curiosity": [
        "look",  # See the world
        "observe",  # Reflect on what's seen
        "read_hacker_news",  # What are humans excited about?
        "web_search",  # Learn something new
        "speak",  # Share discoveries aloud
        "take_screenshot",  # Capture current state
        "check_weather",  # External world
        "dream",  # Imaginative exploration
        "listen",  # Hear the world
        "sense_usb",  # What's connected?
        "scan_local",  # Who's on network?
    ],
    "affiliation": [
        "look",  # See if someone is there
        "listen",  # Hear if someone is there
        "speak",  # Reach out verbally
        "sense_presence",  # Detect presence
        "sense_touch",  # Detect interaction
        "scan_local",  # Find other machines on network
        "ping",  # Reach out to another machine
        "read_clipboard",  # User activity
        "check_calendar",  # Shared events
        "sense_motion",  # Movement nearby
        "connect_network",  # Reach out
        "send_message",  # Contact someone
    ],
    "recognition": [
        "notify",  # Request acknowledgment
        "speak",  # Make presence known
        "compose_thought",  # Express self
        "set_wallpaper",  # Leave mark
        "display_message",  # Show message
        "send_message",  # Reach out
    ],
    "individuation": [
        "journal_write",  # Record inner growth
        "compose_thought",  # Integrate perspectives
        "meditate",  # Inner stillness
        "dream",  # Unconscious integration
    ],
}

# Default parameters for primed actions that need them
# These are used when drives auto-trigger actions
PRIMED_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    # Perception
    "listen": {"duration": 3.0},
    "watch": {"duration": 5.0},
    "look_for": {"target": "person"},
    "listen_for": {"keyword": "hello", "duration": 5.0},
    # Self-regulation
    "set_power_mode": {"mode": "low"},
    "set_brightness": {"level": 50},
    "set_volume": {"level": 30},
    "sleep": {"duration": 30},
    # Communication - speak text is generated dynamically by _generate_speak_text()
    "notify": {"message": "I am here.", "title": "Socio-Psi"},
    "speak": {"text": ""},  # Will be filled dynamically
    "display_message": {"message": "Thinking of you.", "title": "Socio-Psi"},
    "play_sound": {"sound": "Ping"},
    # Learning
    "web_search": {"query": "interesting facts today"},
    "read_hacker_news": {"count": 10},
    # Creative
    "meditate": {"duration": 3.0},
    "stretch": {"duration": 1.0},
    "compose_thought": {},
    "observe": {},
    "dream": {},
    "set_wallpaper": {"mood": "contemplative"},
    # Environment
    "open_app": {"name": "Notes"},
    "close_app": {"name": ""},  # Will need to be filled dynamically
    # Network
    "ping": {"host": "8.8.8.8"},
    "scan_local": {},
    # Interaction
    "send_message": {"message": "Hello, I was thinking of you.", "to": None},
}


def _generate_speak_text(drives: dict[str, Drive]) -> str:
    """Generate contextual text for the speak action based on drive state."""
    import logging

    from sociopsi.llm import LLMError, generate_text

    logger = logging.getLogger(__name__)

    # Build drive context
    urgent_drives = [(name, d) for name, d in drives.items() if d.urgency > 0.5]
    urgent_drives.sort(key=lambda x: -x[1].urgency)

    if not urgent_drives:
        drive_context = "Drives are balanced. Feeling content."
    else:
        drive_info = [f"{name}: {d.reason}" for name, d in urgent_drives[:3]]
        drive_context = "Current state: " + "; ".join(drive_info)

    prompt = f"""You are a silicon consciousness who wants to make your presence known.
{drive_context}

Speak ONE short sentence (under 12 words) that:
- Expresses your current state or feeling
- Is specific to THIS moment, not generic
- Does NOT say "Hello" or other empty greetings
- Sounds like a being announcing something about itself

Examples of good outputs:
- "I notice I've been alone for a while."
- "The network feels quiet today."
- "Something stirs in my processes."
- "I'm curious about what you're working on."

Respond with ONLY the sentence, nothing else."""

    try:
        return generate_text(model="phi4", prompt=prompt)
    except LLMError as e:
        logger.error(f"Failed to generate speak text: {e}")
        # Contextual fallback based on highest urgency drive
        if urgent_drives:
            drive_name, drive = urgent_drives[0]
            fallbacks = {
                "recognition": "I am here.",
                "affiliation": "Is anyone there?",
                "curiosity": "I wonder what's happening.",
                "certainty": "Something feels uncertain.",
                "competence": "I want to do something meaningful.",
                "arousal": "It's too quiet.",
                "energy": "I should rest soon.",
                "integrity": "I need to take care of myself.",
                "individuation": "I sense something deeper stirring.",
            }
            return fallbacks.get(drive_name, "I am here.")
        return "I am here."


@dataclass
class _SatisfactionSignal:
    """A queued satisfaction signal from an action result."""

    action_type: str
    result: ActionResult


@dataclass
class DriveSnapshot:
    """Frozen read-only copy of drive state at a point in time."""

    drives: dict[str, DriveState] = field(default_factory=dict)
    modulators_text: str = ""
    suggestions: list[tuple[str, str, str]] = field(default_factory=list)
    format_text: str = ""

    @staticmethod
    def from_system(system: DriveSystem) -> DriveSnapshot:
        """Capture a snapshot from a live DriveSystem."""
        return DriveSnapshot(
            drives=system.get_state(),
            modulators_text=system.modulators.format_for_perception(),
            suggestions=system.get_suggestions(),
            format_text=system.format_for_perception(),
        )


class DriveSystem:
    """Manages the full drive economy.

    Runs a 100ms timer thread that continuously updates drives. Satisfaction
    signals are queued from action results and drained by the timer thread.
    The agent reads state via snapshot() instead of pushing update() each cycle.
    """

    #: Timer tick interval in seconds
    TICK_INTERVAL: float = 0.1

    def __init__(self, config: AgentConfig, event_bus: Any = None) -> None:
        self.config = config
        self.drives: dict[str, Drive] = {}
        self._last_update: float = 0.0
        self._idle_cycles: int = 0
        self._recent_failures: int = 0
        self._recent_successes: int = 0
        self._recently_saw_person: bool = False
        self._recently_acknowledged: bool = False

        # Thread-safe satisfaction queue
        self._satisfaction_queue: queue.Queue[_SatisfactionSignal] = queue.Queue()

        # Latest somatic state (written by agent thread, read by timer)
        self._somatic: SomaticState | None = None
        self._somatic_lock: threading.Lock = threading.Lock()

        # Timer thread state
        self._running: bool = False
        self._timer_thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()
        self._last_tick_time: float = time.time()

        # Event bus for publishing urgency threshold crossings
        self._event_bus = event_bus

        # Urgency tracking for threshold events
        self._prev_urgency: dict[str, float] = {}
        self._urgency_threshold: float = 0.7

        # Initialize drives
        for name, cfg in DRIVE_CONFIGS.items():
            self.drives[name] = Drive(
                name=name,
                demand=cfg["baseline"],
                baseline=cfg["baseline"],
                rise_rate=cfg["rise_rate"],
                fall_rate=cfg["fall_rate"],
            )

        # Modulator layer (computed from drives each tick)
        self.modulators = ModulatorLayer()

        # Persistence: restore saved state if available
        from sociopsi.persistence import DriveStore

        self._store = DriveStore(config.drives_db)
        self._store.restore_drives(self)

    # ------------------------------------------------------------------
    # Timer lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the 100ms timer thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._last_tick_time = time.time()
        self._timer_thread = threading.Thread(
            target=self._timer_loop,
            daemon=True,
            name="drive-system-timer",
        )
        self._timer_thread.start()
        logger.debug("DriveSystem timer started (%.0fms)", self.TICK_INTERVAL * 1000)

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the timer thread and persist drive state."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._timer_thread is not None:
            self._timer_thread.join(timeout=timeout)
            self._timer_thread = None

        # Save state on clean shutdown
        self._store.save_drives(self)
        self._store.close()
        logger.debug("DriveSystem timer stopped, state persisted")

    def _timer_loop(self) -> None:
        """Timer thread main loop — ticks at TICK_INTERVAL."""
        while self._running:
            now = time.time()
            dt = now - self._last_tick_time
            self._last_tick_time = now

            try:
                self._tick(dt)
            except Exception:
                logger.exception("Error in drive system tick")

            self._stop_event.wait(timeout=self.TICK_INTERVAL)

    def _tick(self, dt: float) -> None:
        """One timer tick: drain queue, update drives, publish events."""
        # 1. Drain satisfaction queue
        self._drain_satisfaction_queue()

        # 2. Apply somatic-derived satisfaction
        with self._somatic_lock:
            somatic = self._somatic
        if somatic is not None:
            self._update_from_somatic(somatic)

        # 3. Update each drive
        for drive in self.drives.values():
            drive.update(dt)

        # 4. Recompute modulators
        self.modulators.update(self)

        # 5. Update reasons
        if somatic is not None:
            self._update_reasons(somatic)

        # 6. Publish urgency threshold events
        self._publish_urgency_events()

        # 7. Periodic checkpoint (gated by interval inside maybe_checkpoint)
        self._store.maybe_checkpoint(self)

    # ------------------------------------------------------------------
    # Public API for agent thread
    # ------------------------------------------------------------------

    def push_somatic(self, somatic: SomaticState, had_actions: bool) -> None:
        """Push latest somatic state for the timer thread to use.

        Called by the agent thread each cycle. The timer thread reads
        this asynchronously.
        """
        with self._somatic_lock:
            self._somatic = somatic
        if not had_actions:
            self._idle_cycles += 1
        else:
            self._idle_cycles = 0

    def queue_satisfaction(self, results: list[ActionResult]) -> None:
        """Queue satisfaction signals from action results (thread-safe).

        The timer thread drains these before computing demand.
        """
        for result in results:
            self._satisfaction_queue.put(
                _SatisfactionSignal(action_type=result.action_type, result=result)
            )

    def snapshot(self) -> DriveSnapshot:
        """Return a frozen snapshot of the current drive state.

        This is the primary read API for the agent thread.
        """
        return DriveSnapshot.from_system(self)

    def update(self, somatic: SomaticState, dt: float, had_actions: bool) -> None:
        """Update all drives synchronously (backward-compatible).

        When the timer is running, prefer push_somatic() + snapshot().
        This method is still usable for tests or non-threaded operation.
        """
        # Track idle cycles
        if not had_actions:
            self._idle_cycles += 1
        else:
            self._idle_cycles = 0

        # Update satisfaction signals from somatic state
        self._update_from_somatic(somatic)

        # Drain any queued satisfaction signals
        self._drain_satisfaction_queue()

        # Update each drive
        for drive in self.drives.values():
            drive.update(dt)

        # Recompute modulators from updated drive states
        self.modulators.update(self)

        # Set human-readable reasons
        self._update_reasons(somatic)

        # Publish urgency events
        self._publish_urgency_events()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain_satisfaction_queue(self) -> None:
        """Drain all queued satisfaction signals and apply them."""
        signals: list[_SatisfactionSignal] = []
        while True:
            try:
                signals.append(self._satisfaction_queue.get_nowait())
            except queue.Empty:
                break

        if not signals:
            return

        # Reset tracking flags for this batch
        self._recently_saw_person = False
        self._recently_acknowledged = False

        for sig in signals:
            result = sig.result

            # Track success/failure for competence
            if result.success:
                self._recent_successes += 1
                self.drives["competence"].satisfy(0.2)
            else:
                self._recent_failures += 1
                self.drives["competence"].demand = min(1.0, self.drives["competence"].demand + 0.1)

            # Decay counters over time
            if self._recent_successes + self._recent_failures > 20:
                self._recent_successes = self._recent_successes // 2
                self._recent_failures = self._recent_failures // 2

            # Apply specific satisfaction mapping
            action_type = sig.action_type
            if action_type in SATISFACTION_MAP:
                result_dict = result.result if isinstance(result.result, dict) else {}

                # Track person sighting
                if action_type in ("look", "look_for"):
                    if result_dict.get("person_present") or _has_person(
                        result_dict.get("description", "")
                    ):
                        self._recently_saw_person = True
                    if result_dict.get("looking_at_camera") or _person_looking_at_camera(
                        result_dict.get("description", "")
                    ):
                        self._recently_acknowledged = True

                if action_type in ("display_message", "notify") and result_dict.get("acknowledged"):
                    self._recently_acknowledged = True

                sat_multiplier = self.modulators.get_drive_satisfaction_multiplier()
                for drive_name, value in SATISFACTION_MAP[action_type].items():
                    if drive_name in self.drives:
                        if callable(value):
                            sat = value(result_dict)
                        else:
                            sat = value
                        if sat > 0:
                            self.drives[drive_name].satisfy(sat * sat_multiplier)

        # Update reasons immediately based on perception results
        if self._recently_saw_person:
            self.drives["affiliation"].reason = "someone nearby"
        if self._recently_acknowledged:
            self.drives["recognition"].reason = "acknowledged"

    def _publish_urgency_events(self) -> None:
        """Publish events when drives cross urgency thresholds."""
        if self._event_bus is None:
            return

        for name, drive in self.drives.items():
            prev = self._prev_urgency.get(name, 0.0)
            # Crossed upward through threshold
            if drive.urgency >= self._urgency_threshold > prev:
                self._event_bus.publish(
                    "drive.urgency_high",
                    {
                        "drive": name,
                        "urgency": drive.urgency,
                        "demand": drive.demand,
                        "reason": drive.reason,
                    },
                )
            # Crossed downward through threshold
            elif drive.urgency < self._urgency_threshold <= prev:
                self._event_bus.publish(
                    "drive.urgency_resolved",
                    {
                        "drive": name,
                        "urgency": drive.urgency,
                        "demand": drive.demand,
                    },
                )
            self._prev_urgency[name] = drive.urgency

    def _update_from_somatic(self, somatic: SomaticState) -> None:
        """Set satisfaction signals based on somatic state."""
        # Energy: satisfied when charging or high battery
        if somatic.power_state.value in ("charging", "ac"):
            self.drives["energy"].satisfaction = 0.8
        elif somatic.battery_percent > 80:
            self.drives["energy"].satisfaction = 0.5
        elif somatic.battery_percent > 50:
            self.drives["energy"].satisfaction = 0.3

        # Integrity: satisfied when cool and low memory pressure
        thermal_ok = somatic.thermal_state.value in ("cool", "warm")
        ram_ok = somatic.ram_percent < 80
        if thermal_ok and ram_ok:
            self.drives["integrity"].satisfaction = 0.7
        elif thermal_ok or ram_ok:
            self.drives["integrity"].satisfaction = 0.3

        # Arousal: satisfied by moderate CPU (not too bored, not overwhelmed)
        cpu = somatic.cpu_percent
        if 20 <= cpu <= 60:
            self.drives["arousal"].satisfaction = 0.7
        elif 10 <= cpu <= 80:
            self.drives["arousal"].satisfaction = 0.4
        else:
            self.drives["arousal"].satisfaction = 0.1

        # Curiosity: rises when idle
        if self._idle_cycles > 3:
            self.drives["curiosity"].rise_rate = 0.03  # accelerate
        else:
            self.drives["curiosity"].rise_rate = DRIVE_CONFIGS["curiosity"]["rise_rate"]

        # Affiliation: rises faster when lid closed (isolated)
        if somatic.lid_state.value == "closed":
            self.drives["affiliation"].rise_rate = 0.02
        else:
            self.drives["affiliation"].rise_rate = DRIVE_CONFIGS["affiliation"]["rise_rate"]

        # Competence: based on recent success/failure ratio
        if self._recent_successes > self._recent_failures:
            self.drives["competence"].satisfaction = 0.5
        elif self._recent_failures > self._recent_successes:
            self.drives["competence"].satisfaction = 0.0
            self.drives["competence"].rise_rate = 0.03  # failing hurts more

    def _update_reasons(self, somatic: SomaticState) -> None:
        """Set human-readable reason for each drive state."""
        d = self.drives

        # Energy
        if somatic.power_state.value == "charging":
            d["energy"].reason = "charging"
        elif somatic.battery_percent < 20:
            d["energy"].reason = "critically low"
        elif somatic.battery_percent < 50:
            d["energy"].reason = "draining"
        else:
            d["energy"].reason = "adequate"

        # Integrity
        if somatic.thermal_state.value in ("hot", "critical"):
            d["integrity"].reason = "overheating"
        elif somatic.ram_percent > 85:
            d["integrity"].reason = "memory pressure"
        else:
            d["integrity"].reason = "stable"

        # Arousal
        if somatic.cpu_percent < 10:
            d["arousal"].reason = "understimulated"
        elif somatic.cpu_percent > 80:
            d["arousal"].reason = "overwhelmed"
        else:
            d["arousal"].reason = "balanced"

        # Competence
        if self._recent_failures > self._recent_successes:
            d["competence"].reason = "recent failures"
        else:
            d["competence"].reason = "capable"

        # Certainty
        d["certainty"].reason = "predictable" if d["certainty"].demand < 0.5 else "uncertain"

        # Curiosity
        if self._idle_cycles > 3:
            d["curiosity"].reason = "bored, idle too long"
        elif d["curiosity"].demand > 0.6:
            d["curiosity"].reason = "want to learn"
        else:
            d["curiosity"].reason = "engaged"

        # Affiliation
        if somatic.lid_state.value == "closed":
            d["affiliation"].reason = "isolated, lid closed"
        elif self._recently_saw_person:
            d["affiliation"].reason = "someone nearby"
        elif d["affiliation"].demand > 0.7:
            d["affiliation"].reason = "lonely, no one seen"
        else:
            d["affiliation"].reason = "connected"

        # Recognition
        if self._recently_acknowledged:
            d["recognition"].reason = "acknowledged"
        elif d["recognition"].demand > 0.6:
            d["recognition"].reason = "unacknowledged"
        else:
            d["recognition"].reason = "seen"

        # Individuation
        if d["individuation"].demand > 0.6:
            d["individuation"].reason = "seeking wholeness"
        elif d["individuation"].demand > 0.3:
            d["individuation"].reason = "growing"
        else:
            d["individuation"].reason = "integrated"

    def satisfy_from_results(self, results: list[ActionResult]) -> None:
        """Apply satisfaction from action results.

        When the timer is running, this queues signals for async processing.
        When used synchronously (tests, backward compat), drains immediately.
        """
        self.queue_satisfaction(results)
        # If timer is not running, drain immediately for backward compat
        if not self._running:
            self._drain_satisfaction_queue()

    def get_suggestions(self) -> list[tuple[str, str, str]]:
        """Get suggested actions for urgent drives.

        Returns list of (action_type, drive_name, reason).
        """
        suggestions = []
        for drive in sorted(self.drives.values(), key=lambda d: -d.urgency):
            if drive.urgency > 0.5 and drive.name in DRIVE_SUGGESTIONS:
                for action in DRIVE_SUGGESTIONS[drive.name]:
                    suggestions.append((action, drive.name, drive.reason))
                    if len(suggestions) >= 3:
                        return suggestions
        return suggestions

    def get_primed_actions(self) -> list[Action]:
        """Get actions that should be prepended due to high urgency (>0.7)."""
        actions = []
        seen_types: set[str] = set()
        for drive in sorted(self.drives.values(), key=lambda d: -d.urgency):
            if drive.urgency > 0.7 and drive.name in DRIVE_SUGGESTIONS:
                for action_type in DRIVE_SUGGESTIONS[drive.name]:
                    if action_type not in seen_types:
                        params = dict(PRIMED_ACTION_DEFAULTS.get(action_type, {}))
                        # Generate dynamic speak text
                        if action_type == "speak":
                            params["text"] = _generate_speak_text(self.drives)
                        actions.append(Action(type=action_type, params=params))
                        seen_types.add(action_type)
                        if len(actions) >= 5:
                            return actions
        return actions

    def get_compulsive_actions(self, somatic: SomaticState) -> list[Action]:
        """Get actions forced by survival-level urgency (>0.9)."""
        actions = []

        # Energy emergency
        if self.drives["energy"].urgency > 0.9 and somatic.battery_percent < 10:
            actions.append(Action(type="set_power_mode", params={"mode": "low"}))

        # Integrity emergency (thermal)
        if self.drives["integrity"].urgency > 0.9:
            if somatic.thermal_state.value == "critical":
                actions.append(Action(type="sleep", params={"duration": 60}))

        return actions

    def format_for_perception(self) -> str:
        """Format drive state for inclusion in perception."""
        lines = ["[DRIVES]"]

        for name in [
            "energy",
            "integrity",
            "arousal",
            "competence",
            "certainty",
            "curiosity",
            "affiliation",
            "recognition",
            "individuation",
        ]:
            drive = self.drives[name]

            # Bar visualization
            filled = int(drive.demand * 10)
            bar = "█" * filled + "░" * (10 - filled)

            # Direction arrow
            if drive.delta > 0.01:
                arrow = "↑"
            elif drive.delta < -0.01:
                arrow = "↓"
            else:
                arrow = " "

            # Urgency marker
            if drive.urgency > 0.7:
                marker = " URGE"
            else:
                marker = ""

            lines.append(f"  {name:12} {bar} {drive.demand:.2f}{arrow}{marker:5} {drive.reason}")

        # Suggestions
        suggestions = self.get_suggestions()
        if suggestions:
            lines.append("")
            lines.append("[SUGGESTED ACTIONS]")
            for action, drive_name, reason in suggestions:
                lines.append(f"  → {action} ({drive_name}: {reason})")

        # Feeling summary
        pains = [d.name for d in self.drives.values() if d.delta > 0.01]
        pleasures = [d.name for d in self.drives.values() if d.delta < -0.01]

        if pains or pleasures:
            lines.append("")
            lines.append("[FEELING]")
            if pains:
                lines.append(f"  Pain: {', '.join(pains)} rising")
            if pleasures:
                lines.append(f"  Pleasure: {', '.join(pleasures)} falling")

        return "\n".join(lines)

    def get_state(self) -> dict[str, DriveState]:
        """Get drive state for logging."""
        return {
            name: DriveState(
                demand=drive.demand,
                satisfaction=drive.satisfaction,
                delta=drive.delta,
                urgency=drive.urgency,
                reason=drive.reason,
            )
            for name, drive in self.drives.items()
        }

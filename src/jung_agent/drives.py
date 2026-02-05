"""Psi drive system - motivational economy based on Joscha Bach's Psi theory."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from jung_agent.config import AgentConfig
from jung_agent.types import Action, ActionResult, SomaticState

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

    def update(self, dt: float) -> None:
        """Update demand based on time and satisfaction."""
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

        # Reset satisfaction for next tick (must be re-supplied)
        self.satisfaction = 0.0

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
    """Check if vision description mentions a person."""
    desc_lower = description.lower()
    return any(word in desc_lower for word in ["person", "man", "woman", "someone", "human"])


# Satisfaction mapping: action_type -> {drive_name -> satisfaction_value_or_callable}
SatisfactionValue = float | Callable[[dict[str, Any]], float]
SATISFACTION_MAP: dict[str, dict[str, SatisfactionValue]] = {
    # Homeostatic
    "check_battery": {
        "energy": lambda r: 0.3 if r.get("power_state") == "charging" else 0.1,
    },
    "set_power_mode": {
        "energy": lambda r: 0.2 if r.get("mode") == "low" else 0,
    },
    "check_thermals": {
        "integrity": lambda r: 0.2 if r.get("state") in ("cool", "warm") else 0,
    },
    "check_memory": {
        "integrity": lambda r: 0.2 if r.get("percent", 100) < 80 else 0,
    },
    # Cognitive
    "web_search": {
        "curiosity": lambda r: 0.5 if r.get("results") else 0.1,
    },
    "web_read": {
        "curiosity": lambda r: 0.6 if r.get("content") else 0.1,
    },
    "journal_write": {
        "curiosity": 0.2,
        "competence": 0.1,
    },
    "journal_read": {
        "curiosity": 0.3,
    },
    "recall_memory": {
        "certainty": 0.2,
    },
    # Social - depends on what was perceived
    "look": {
        "affiliation": lambda r: 0.7 if _has_person(r.get("description", "")) else 0,
        "recognition": lambda r: 0.8 if _person_looking_at_camera(r.get("description", "")) else 0,
        "curiosity": 0.2,
    },
    "look_for": {
        "affiliation": lambda r: 0.7 if _has_person(r.get("description", "")) else 0,
        "recognition": lambda r: 0.8 if _person_looking_at_camera(r.get("description", "")) else 0,
        "curiosity": 0.3,
    },
    "listen": {
        "affiliation": lambda r: 0.5 if r.get("rms_level", 0) > 0.05 else 0,
        "curiosity": 0.1,
    },
    "transcribe": {
        "affiliation": lambda r: 0.8 if r.get("transcription") else 0,
        "curiosity": 0.2,
    },
    "sense_presence": {
        "affiliation": lambda r: 0.3 if r.get("count", 0) > 0 else 0,
    },
    # Communication
    "speak": {
        "recognition": 0.2,
    },
    "notify": {
        "recognition": 0.3,
    },
    "display_message": {
        "recognition": lambda r: 0.7 if r.get("acknowledged") else 0.1,
    },
}

# Actions suggested for each drive when urgent
DRIVE_SUGGESTIONS: dict[str, list[str]] = {
    "energy": ["check_battery", "set_power_mode"],
    "integrity": ["check_thermals", "check_memory"],
    "arousal": ["sense_all", "check_processes"],
    "competence": [],  # satisfied by any successful action
    "certainty": ["sense_all", "journal_read"],  # removed recall_memory (needs key)
    "curiosity": ["look", "journal_read"],  # removed web_search (needs query)
    "affiliation": ["look", "listen", "sense_presence"],
    "recognition": ["notify"],  # removed speak (needs text)
}

# Default parameters for primed actions that need them
PRIMED_ACTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "listen": {"duration": 3.0},
    "set_power_mode": {"mode": "low"},
    "notify": {"message": "I am here.", "title": "Jung"},
}


class DriveSystem:
    """Manages the full drive economy."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.drives: dict[str, Drive] = {}
        self._last_update: float = 0.0
        self._idle_cycles: int = 0
        self._recent_failures: int = 0
        self._recent_successes: int = 0
        self._recently_saw_person: bool = False  # Track if person was seen recently
        self._recently_acknowledged: bool = False  # Track if user acknowledged us

        # Initialize drives
        for name, cfg in DRIVE_CONFIGS.items():
            self.drives[name] = Drive(
                name=name,
                demand=cfg["baseline"],  # Start at baseline
                baseline=cfg["baseline"],
                rise_rate=cfg["rise_rate"],
                fall_rate=cfg["fall_rate"],
            )

    def update(self, somatic: SomaticState, dt: float, had_actions: bool) -> None:
        """Update all drives based on somatic state and time elapsed."""
        # Track idle cycles
        if not had_actions:
            self._idle_cycles += 1
        else:
            self._idle_cycles = 0

        # Update satisfaction signals from somatic state
        self._update_from_somatic(somatic)

        # Update each drive
        for drive in self.drives.values():
            drive.update(dt)

        # Set human-readable reasons
        self._update_reasons(somatic)

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

    def satisfy_from_results(self, results: list[ActionResult]) -> None:
        """Apply satisfaction from action results."""
        # Reset tracking flags at start of new results processing
        self._recently_saw_person = False
        self._recently_acknowledged = False

        for result in results:
            action_type = result.action_type

            # Track success/failure for competence
            if result.success:
                self._recent_successes += 1
                # General competence satisfaction for any success
                self.drives["competence"].satisfy(0.2)
            else:
                self._recent_failures += 1
                # Failure increases competence demand (via negative satisfaction effect)
                self.drives["competence"].demand = min(1.0, self.drives["competence"].demand + 0.1)

            # Decay counters over time
            if self._recent_successes + self._recent_failures > 20:
                self._recent_successes = self._recent_successes // 2
                self._recent_failures = self._recent_failures // 2

            # Apply specific satisfaction mapping
            if action_type in SATISFACTION_MAP:
                result_dict = result.result if isinstance(result.result, dict) else {}

                # Track if we saw a person (for affiliation reason updates)
                if action_type in ("look", "look_for"):
                    description = result_dict.get("description", "")
                    if _has_person(description):
                        self._recently_saw_person = True
                    if _person_looking_at_camera(description):
                        self._recently_acknowledged = True

                # Track if user acknowledged a message
                if action_type == "display_message" and result_dict.get("acknowledged"):
                    self._recently_acknowledged = True

                for drive_name, value in SATISFACTION_MAP[action_type].items():
                    if drive_name in self.drives:
                        if callable(value):
                            sat = value(result_dict)
                        else:
                            sat = value
                        if sat > 0:
                            self.drives[drive_name].satisfy(sat)

        # Update reasons immediately based on perception results
        if self._recently_saw_person:
            self.drives["affiliation"].reason = "someone nearby"
        if self._recently_acknowledged:
            self.drives["recognition"].reason = "acknowledged"

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
                        params = PRIMED_ACTION_DEFAULTS.get(action_type, {})
                        actions.append(Action(type=action_type, params=dict(params)))
                        seen_types.add(action_type)
                        if len(actions) >= 2:
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

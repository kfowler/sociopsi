"""Logging for perceptions, drives, and state."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from jung_agent.config import AgentConfig
from jung_agent.types import ActionResult, SomaticState, StreamSegment

# Type alias for drive state levels
DriveStateLevel = Literal["dormant", "low", "moderate", "active", "intense"]


class PsycheLogger:
    """Logs the psyche's perceptions, drives, and state."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.log_dir = Path(config.data_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Current session log file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{self.session_id}.jsonl"

        # Drive tracking (accumulated over session)
        self._action_counts: dict[str, int] = {}
        self._last_user_interaction: datetime | None = None
        self._idle_cycles: int = 0

    def log_cycle(
        self,
        perception: str,
        somatic: SomaticState,
        stream: list[StreamSegment],
        actions: list[str],
        action_results: list[ActionResult],
        heartbeat_interval: int,
        heartbeat_mode: str,
        drives: dict[str, Any] | None = None,
    ) -> None:
        """Log a complete perception-response cycle."""
        now = datetime.now()

        # Update action counts
        for action in actions:
            self._action_counts[action] = self._action_counts.get(action, 0) + 1

        # Track idle cycles
        if not actions:
            self._idle_cycles += 1
        else:
            self._idle_cycles = 0

        # Use provided drives or compute legacy
        if drives is None:
            drives = self._compute_drives(somatic, actions)

        entry = {
            "timestamp": now.isoformat(),
            "perception": perception,
            "somatic": {
                "battery": somatic.battery_percent,
                "cpu": somatic.cpu_percent,
                "ram": somatic.ram_percent,
                "thermal": somatic.thermal_state.value,
                "network": somatic.network_state.value,
                "lid": somatic.lid_state.value,
                "power": somatic.power_state.value,
                "fan_rpm": somatic.fan_rpm,
            },
            "stream": [{"component": s.component, "text": s.text} for s in stream],
            "actions": actions,
            "action_results": [
                {
                    "type": r.action_type,
                    "success": r.success,
                    "error": r.error,
                }
                for r in action_results
            ],
            "drives": drives,
            "heartbeat": {
                "interval": heartbeat_interval,
                "mode": heartbeat_mode,
            },
        }

        # Write to log file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _compute_drives(self, somatic: SomaticState, actions: list[str]) -> dict[str, Any]:
        """Compute current drive states based on activity and somatic state."""
        # USEFULNESS: Based on CPU activity and recent actions
        usefulness_score = min(100, somatic.cpu_percent + len(actions) * 10)
        if self._idle_cycles > 5:
            usefulness_score = max(0, usefulness_score - self._idle_cycles * 5)

        # BUSYNESS: Based on CPU, RAM, and action frequency
        busyness_score = (somatic.cpu_percent + somatic.ram_percent) / 2
        total_actions = sum(self._action_counts.values())
        if total_actions > 10:
            busyness_score = min(100, busyness_score + 20)

        # CONNECTION (Machines): Based on network state and network-related actions
        network_actions = sum(
            self._action_counts.get(a, 0)
            for a in ["ping", "probe", "scan_local", "sense_network", "sense_presence"]
        )
        machine_connection = 50 if somatic.network_state.value == "connected" else 10
        machine_connection = min(100, machine_connection + network_actions * 5)

        # CONNECTION (Humans): Based on interaction actions
        human_actions = sum(
            self._action_counts.get(a, 0)
            for a in ["speak", "notify", "display_message", "look", "listen", "transcribe"]
        )
        human_connection = min(100, human_actions * 10)
        if somatic.lid_state.value == "closed":
            human_connection = max(0, human_connection - 30)

        # CURIOSITY: Based on learning actions
        learning_actions = sum(
            self._action_counts.get(a, 0)
            for a in ["web_search", "web_read", "describe_image", "journal_read", "recall_memory"]
        )
        curiosity_score = min(100, learning_actions * 15)
        if self._idle_cycles > 3:
            curiosity_score = min(100, curiosity_score + 20)  # Boredom increases curiosity

        return {
            "usefulness": {
                "score": usefulness_score,
                "state": _drive_state(usefulness_score),
            },
            "busyness": {
                "score": busyness_score,
                "state": _drive_state(busyness_score),
            },
            "connection_machines": {
                "score": machine_connection,
                "state": _drive_state(machine_connection),
            },
            "connection_humans": {
                "score": human_connection,
                "state": _drive_state(human_connection),
            },
            "curiosity": {
                "score": curiosity_score,
                "state": _drive_state(curiosity_score),
            },
            "idle_cycles": self._idle_cycles,
            "total_actions": sum(self._action_counts.values()),
        }

    def get_session_log(self) -> Path:
        """Return the current session log file path."""
        return self.log_file


def _drive_state(score: float) -> DriveStateLevel:
    """Convert drive score to descriptive state."""
    if score < 20:
        return "dormant"
    elif score < 40:
        return "low"
    elif score < 60:
        return "moderate"
    elif score < 80:
        return "active"
    else:
        return "intense"

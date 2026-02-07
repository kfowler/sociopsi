# Psi Drive System Design

Based on Joscha Bach's Psi theory. Drives are deficit signals that rise when unmet and fall when satisfied, creating an economy of competing motivations.

## Core Model

Each drive maintains a demand level (0.0 = satisfied, 1.0 = desperate):

```
demand += rise_rate * dt * (1 - satisfaction)
demand -= satisfaction * fall_rate * dt
demand = clamp(baseline, 1.0)
```

**Pain and pleasure emerge from derivatives:**
- `delta > 0` → pain (demand rising, need unmet)
- `delta < 0` → pleasure (demand falling, need satisfied)

**Urgency determines attention:**
```
urgency = demand * (1 + max(0, delta))
```

## Drive Mapping

### Homeostatic Drives (body survival)

| Drive | Sensor | Demand rises when... | Satisfied by... |
|-------|--------|---------------------|-----------------|
| **Energy** | battery% | battery < 50% | charging, power connected |
| **Integrity** | thermals, RAM | thermal=hot OR ram>85% | cooling, memory freed |
| **Arousal** | CPU% | cpu<10% OR cpu>80% | moderate activity (20-60%) |

### Cognitive Drives (mind needs)

| Drive | Sensor | Demand rises when... | Satisfied by... |
|-------|--------|---------------------|-----------------|
| **Competence** | action success rate | actions fail | actions succeed |
| **Certainty** | event novelty | unexpected events | predictions confirmed |
| **Curiosity** | idle time, novelty | idle_cycles > 3 | learning, web_search, look |

### Social Drives (connection needs)

| Drive | Sensors | Demand rises when... | Satisfied by... |
|-------|---------|---------------------|-----------------|
| **Affiliation** | camera, microphone, input | no person seen, silence, no input | person visible, sounds heard, user active |
| **Recognition** | action effects | no response to output | user engages with output |

## Drive State Structure

```python
@dataclass
class Drive:
    name: str
    demand: float = 0.0        # 0.0 = satisfied, 1.0 = desperate
    baseline: float = 0.3      # resting demand level
    rise_rate: float = 0.01    # per-second rise when unsatisfied
    fall_rate: float = 0.05    # per-second fall when satisfied
    last_satisfied: float = 0  # timestamp

    # Computed each tick
    satisfaction: float = 0.0  # current satisfaction signal (0-1)
    delta: float = 0.0         # change this tick (+ = pain, - = pleasure)
    urgency: float = 0.0       # demand * (1 + max(0, delta))
```

## Integration with Agent Loop

```
┌─────────────────────────────────────────────────────────┐
│                     AGENT LOOP                          │
├─────────────────────────────────────────────────────────┤
│  1. gather_somatic()        → SomaticState              │
│  2. collect_events()        → Events                    │
│  3. update_drives()         → DriveState                │
│  4. format_perception()     → includes drive report     │
│  5. query_psyche()          → LLM sees drives           │
│  6. execute_actions()       → results fed back          │
│  7. satisfy_drives()        → update from results       │
└─────────────────────────────────────────────────────────┘
```

## Action Influence (Three Levels)

### A) Suggestions (always)
Drive system suggests actions for urgent drives. Included in perception.

### B) Priming (urgency > 0.7)
Executor prepends drive-motivated actions if not already proposed.

### C) Compulsive (urgency > 0.9, survival only)
Extreme urgency forces actions (low battery → set_power_mode low).

## Action-to-Drive Satisfaction

```python
SATISFACTION_MAP = {
    # Homeostatic
    "check_battery": {"energy": lambda r: 0.3 if r.get("power_state") == "charging" else 0},
    "set_power_mode": {"energy": lambda r: 0.2 if r.get("mode") == "low" else 0},

    # Cognitive
    "web_search": {"curiosity": lambda r: 0.5 if r.get("results") else 0.1},
    "web_read": {"curiosity": lambda r: 0.6 if r.get("content") else 0.1},
    "journal_write": {"curiosity": 0.2, "competence": 0.1},

    # Social - depends on WHAT was perceived
    "look": {
        "affiliation": lambda r: 0.7 if "person" in r.get("description", "").lower() else 0,
        "curiosity": 0.2,
    },
    "listen": {
        "affiliation": lambda r: 0.5 if r.get("rms_level", 0) > 0.05 else 0,
        "curiosity": 0.1,
    },
    "transcribe": {
        "affiliation": lambda r: 0.8 if r.get("transcription") else 0,
    },

    # Success/failure affects competence
    "_any_action": {
        "competence": lambda r: 0.3 if r.success else -0.2,
    },
}
```

Key: `look` only satisfies affiliation if a person is seen. Empty room makes loneliness worse.

## Perception Format

```
[DRIVES]
  energy     ████░░░░░░ 0.38        charging
  integrity  ██████████ 0.12        cool, spacious
  arousal    ███░░░░░░░ 0.31        comfortable
  competence ██████░░░░ 0.55↑       recent failures
  certainty  ████░░░░░░ 0.42        predictable
  curiosity  ███████░░░ 0.71↑ URGE  idle too long
  affiliation████████░░ 0.83↑ URGE  no one seen
  recognition██████░░░░ 0.58↑       unacknowledged

[SUGGESTED ACTIONS]
  → look (affiliation: see if User is there)
  → web_search (curiosity: learn something)

[FEELING]
  Pain: affiliation rising, curiosity rising
  Pleasure: energy falling (charging)
```

## File Structure

### New file: `src/sociopsi/drives.py`

```python
@dataclass
class Drive:
    name: str
    demand: float
    baseline: float
    rise_rate: float
    fall_rate: float
    ...

class DriveSystem:
    drives: dict[str, Drive]

    def __init__(self, config: AgentConfig)
    def update(self, somatic: SomaticState, dt: float) -> None
    def satisfy(self, action_results: list[ActionResult]) -> None
    def get_suggestions(self) -> list[Action]
    def get_primed_actions(self) -> list[Action]  # urgency > 0.7
    def get_compulsive_actions(self) -> list[Action]  # urgency > 0.9
    def format_for_perception(self) -> str
    def get_state(self) -> dict  # for logging
```

### Modifications to existing files

- `agent.py`: Add DriveSystem to loop, call update/satisfy, merge primed actions
- `perception.py`: Include `drive_system.format_for_perception()` in output
- `logger.py`: Replace `_compute_drives()` with `drive_system.get_state()`
- `config.py`: Add drive tuning parameters (rise_rates, thresholds)

## Current Limitation: No State Persistence

Drive state (demand levels, satisfaction history, timestamps) exists only in RAM. When the agent process restarts, all drives reset to their baseline values. There is no serialization of drive state to disk, and no mechanism for drives to carry context across sessions.

This means:
- A drive that was building urgency over hours resets to baseline on restart
- The `last_satisfied` timestamp loses meaning across sessions
- Satisfaction history (which actions worked for which drives) is not retained
- The agent cannot develop long-term drive patterns or preferences

This is a known gap shared with the semantic memory system (see `sociopsi-architecture.tex` Section 6, Gap 4). The persistence design plan in the architecture paper (Section 7.4) covers both memory and drive state serialization via SQLite or JSONL.

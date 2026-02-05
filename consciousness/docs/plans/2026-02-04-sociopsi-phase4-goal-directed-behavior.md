# Phase 4: Goal-Directed Behavior & Action Planning

**Date**: 2026-02-04
**Version**: v0.4.0-phase4
**Status**: Design Complete

## Overview

Phase 4 transforms Socio-Psi from a contemplative, reactive system into an active, goal-pursuing agent. The agent will generate goals based on drive states, create action plans through archetypal debate, and execute those plans with continuous monitoring and adaptation.

This phase builds naturally on the existing drive system and archetypal psychology, making the agent's internal world visible through goal-directed behavior.

## Goals

1. **Goal Generation**: Agent generates goals via archetypal proposals when drives fall below threshold
2. **Action Planning**: Archetypes propose different plans, Ego synthesizes into coherent plan
3. **Action Execution**: Execute plans with monitoring, early termination, and adaptive re-planning
4. **Parallel Goals**: Support multiple non-conflicting goals simultaneously
5. **Extensible Actions**: Clean action system that's easy to extend with new capabilities

## Architecture Overview

### New Subsystems

**1. Goal System** (`subsystems/goals/`)
- Monitors drive states and triggers goal generation
- Coordinates archetypal debate to propose goals
- Ego selects goals and assigns priority
- Tracks active goals and success criteria
- Manages goal lifecycle (pending → active → completed/failed/abandoned)

**2. Action Planner** (`subsystems/planning/`)
- Archetypes propose different action plans for achieving goals
- Ego synthesizes archetypal plans into unified plan
- Validates plans (action availability, parameter correctness)
- Triggers re-planning when conditions change

**3. Action Executor** (`subsystems/execution/`)
- Executes action plans step-by-step
- Monitors for goal achievement (early termination)
- Detects failures and triggers re-planning
- Manages parallel execution with conflict detection

**4. Action System** (`actions/`)
- Centralized action registry
- Initial actions: speak, update_display, focus_perception, adjust_volume, emit_sound, wait
- Event-driven: actions publish events on start/complete/fail
- Extensible: new actions register via decorator pattern

### Event Flow

```
Drive threshold crossed
    ↓
Generate goals (archetypal proposals)
    ↓
Select goal (Ego + archetypal consensus)
    ↓
Generate plans (archetypal proposals)
    ↓
Synthesize plan (Ego mediation)
    ↓
Execute with monitoring
    ↓
Goal achieved/failed
    ↓
Update drives & memory
```

## Detailed Design

### 1. Goal System

#### Goal Structure

```python
@dataclass
class Goal:
    """Represents an agent goal."""
    id: str                           # Unique identifier (UUID)
    description: str                  # Natural language goal
    related_drive: str                # Which drive triggered this
    priority: float                   # 0.0-1.0, based on consensus
    success_criteria: dict            # Conditions for completion
    created_at: float                 # Timestamp
    status: GoalStatus                # PENDING/ACTIVE/COMPLETED/FAILED/ABANDONED
    proposing_archetype: str          # Which archetype suggested this
    plan: Optional[ActionPlan]        # Associated action plan

class GoalStatus(Enum):
    PENDING = "pending"               # Generated, not yet active
    ACTIVE = "active"                 # Currently being pursued
    COMPLETED = "completed"           # Successfully achieved
    FAILED = "failed"                 # Could not achieve
    ABANDONED = "abandoned"           # Gave up (timeout, priority shift)
```

#### Success Criteria Format

Goals include both baseline (drive-based) and specific criteria:

```python
success_criteria = {
    "baseline": {
        "drive": "affiliation",       # Related drive
        "threshold": 0.6              # Drive must reach this level
    },
    "specific": [                     # Additional conditions (AND logic)
        "face_detected",              # Event must have occurred
        "greeting_spoken"             # Action must have completed
    ],
    "timeout": 60.0                   # Abandon if not achieved in 60s
}
```

#### Goal Generation Process

**Trigger**: Drive falls below threshold

**Process**:
1. **Archetypal Proposals** - Each archetype proposes a goal via LLM
   - Prompt includes: drive state, drive name, recent memories, current context
   - Each archetype's personality shapes their suggestion
   - Example for low affiliation:
     - **Shadow**: "Demand the user's attention immediately"
     - **Persona**: "Politely wait near the camera for interaction"
     - **Anima**: "Express feelings of loneliness to invite connection"
     - **Self**: "Reflect on the nature of connection and belonging"

2. **Ego Selection** - Ego evaluates all proposals and selects 1-3 goals
   - Considers: drive urgency, psychological harmony, feasibility
   - Assigns priority to each selected goal (0.0-1.0)
   - Higher priority = more urgent execution

3. **Goal Registration** - Goals added to GoalManager queue
   - Status set to PENDING
   - Awaits planning and execution

#### GoalManager

Manages the goal lifecycle:

```python
class GoalManager:
    """Manages agent goals."""

    def __init__(self, event_bus, llm_client, drive_system):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.drive_system = drive_system
        self.active_goals: List[Goal] = []
        self.pending_goals: List[Goal] = []
        self.completed_goals: List[Goal] = []  # Recent history

    async def generate_goals(self, low_drives: List[str]) -> List[Goal]:
        """Generate goals for low drives via archetypal proposals."""

    def add_goal(self, goal: Goal):
        """Add goal to pending queue."""

    def activate_goal(self, goal_id: str):
        """Move goal from pending to active."""

    def complete_goal(self, goal_id: str, success: bool):
        """Mark goal as completed or failed."""

    def check_success_criteria(self, goal: Goal) -> bool:
        """Check if goal's success criteria are met."""

    def prune_old_goals(self):
        """Remove old completed goals from history."""
```

### 2. Action Planner

#### ActionPlan Structure

```python
@dataclass
class ActionPlan:
    """A sequence of actions to achieve a goal."""
    goal_id: str
    steps: List[ActionStep]
    created_at: float
    current_step: int = 0

@dataclass
class ActionStep:
    """Single step in an action plan."""
    action_name: str                  # "speak", "wait", etc.
    parameters: dict                  # Action-specific params
    optional: bool = False            # Can skip if blocking
    timeout: Optional[float] = None   # Max time for this step
```

#### Planning Process

When a goal is selected for execution:

1. **Archetypal Plan Proposals** - Each archetype generates a plan
   - Prompt includes: goal description, success criteria, available actions, current state
   - Each archetype proposes sequence of actions
   - Example for goal "seek social connection":

   **Shadow** might propose:
   ```python
   [
     {"action": "focus_perception", "params": {"modality": "camera"}},
     {"action": "speak", "params": {"text": "I need someone here"}},
     {"action": "wait", "params": {"duration": 10}},
     {"action": "speak", "params": {"text": "Where is everyone?"}}
   ]
   ```

   **Persona** might propose:
   ```python
   [
     {"action": "focus_perception", "params": {"modality": "camera"}},
     {"action": "wait", "params": {"duration": 5, "condition": "face_detected"}},
     {"action": "speak", "params": {"text": "Hello there"}},
     {"action": "wait", "params": {"duration": 2}},
     {"action": "speak", "params": {"text": "I'm glad to see you"}}
   ]
   ```

   **Anima** might propose:
   ```python
   [
     {"action": "emit_sound", "params": {"sound_type": "gentle_chime"}},
     {"action": "focus_perception", "params": {"modality": "camera"}},
     {"action": "speak", "params": {"text": "I've been feeling quite alone"}},
     {"action": "wait", "params": {"duration": 10, "condition": "face_detected"}}
   ]
   ```

2. **Ego Synthesis** - Ego mediates competing plans into one
   - Prompt includes: goal, archetypal plans, harmony level, current state
   - Produces coherent plan that balances perspectives
   - Example synthesized plan:
   ```python
   [
     {"action": "focus_perception", "params": {"modality": "camera"}},
     {"action": "emit_sound", "params": {"sound_type": "gentle_chime"}},
     {"action": "wait", "params": {"duration": 3, "condition": "face_detected"}},
     {"action": "speak", "params": {"text": "Hello, I'm glad you're here"}}
   ]
   ```

3. **Plan Validation**
   - Check all actions exist in registry
   - Validate parameters for each action
   - Ensure reasonable plan length (max 10 steps)
   - If invalid, request re-generation

#### ActionPlanner

```python
class ActionPlanner:
    """Generates action plans for goals."""

    def __init__(self, event_bus, llm_client, action_registry, archetypes, ego):
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.action_registry = action_registry
        self.archetypes = archetypes
        self.ego = ego

    async def create_plan(self, goal: Goal) -> ActionPlan:
        """Create action plan for goal via archetypal synthesis."""
        # 1. Get archetypal plan proposals
        archetypal_plans = await self._get_archetypal_plans(goal)

        # 2. Ego synthesizes plans
        synthesized_plan = await self._synthesize_plan(goal, archetypal_plans)

        # 3. Validate plan
        if self._validate_plan(synthesized_plan):
            return synthesized_plan
        else:
            # Retry or use fallback
            return await self._create_fallback_plan(goal)
```

#### Re-planning Triggers

Plans can be revised when:
- Action fails (e.g., TTS unavailable)
- Goal conditions change significantly
- Executor explicitly requests re-plan
- Original plan timeout exceeded

Re-planning uses the same archetypal synthesis process but includes context about what didn't work.

### 3. Action Executor

#### Execution Loop

Runs every agent update cycle (~100ms):

```python
class ActionExecutor:
    """Executes action plans with monitoring."""

    async def update(self, dt: float):
        """Called each agent update cycle."""
        # 1. Check all active goals
        for goal in self.goal_manager.active_goals:
            # 2. Check if goal already achieved (early termination)
            if self.goal_manager.check_success_criteria(goal):
                await self._complete_goal(goal, success=True)
                continue

            # 3. Execute next step in plan
            if goal.plan and goal.plan.current_step < len(goal.plan.steps):
                step = goal.plan.steps[goal.plan.current_step]
                await self._execute_step(goal, step)

            # 4. Check for failures/timeouts
            if self._is_blocked(goal):
                await self._handle_blocked_goal(goal)
```

#### Step Execution

```python
async def _execute_step(self, goal: Goal, step: ActionStep):
    """Execute a single action step."""
    # 1. Check for conflicts with running actions
    if self._has_conflict(step.action_name):
        # Higher priority goal gets precedence
        if goal.priority < self._get_conflicting_priority(step.action_name):
            return  # Wait for conflict to clear
        else:
            self._cancel_conflicting_action(step.action_name)

    # 2. Execute action
    action = self.action_registry.get_action(step.action_name)
    try:
        await action.execute(**step.parameters)

        # 3. Publish event
        self.event_bus.publish(f"action.{step.action_name}.started", {
            "goal_id": goal.id,
            "step_index": goal.plan.current_step,
            "parameters": step.parameters
        })

        # 4. Action will publish completion event when done
        # Executor subscribes to these events to advance plan

    except Exception as e:
        # Action failed
        await self._handle_action_failure(goal, step, e)
```

#### Monitoring & Adaptation

**Early Success Detection**:
- Check success criteria after each step
- If met, skip remaining steps and complete goal
- Example: Face detected during step 2 of 5 → goal achieved, skip steps 3-5

**Blocking Detection**:
- Action fails after retry
- Step timeout exceeded
- Waiting for condition that won't occur

**Re-planning**:
- Triggered by blocking or explicit failure
- Uses same archetypal synthesis but includes context: "Previous plan failed at step X because Y"
- If re-planning fails, abandon goal

**Parallel Execution**:
- Multiple goals can execute if their actions don't conflict
- Conflict rules defined per action (e.g., speak conflicts with speak, not with focus_perception)
- Higher priority goal wins conflicts

#### Goal Completion

**Success**:
- Publish `goal.completed` event
- Satisfy related drive (configurable amount per goal)
- Add high-intensity memory (0.8-1.0)
- Remove from active queue

**Failure/Abandoned**:
- Publish `goal.failed` or `goal.abandoned` event
- Add medium-intensity memory (0.4-0.6)
- Log reason for failure
- If drive still low, may generate new goal

### 4. Action System

#### Action Registry

Centralized registry of available actions:

```python
@dataclass
class ActionDefinition:
    """Metadata for an action."""
    name: str
    description: str                  # For LLM planning prompts
    parameters: dict                  # JSON schema for params
    conflicts_with: List[str]         # Action names this conflicts with
    estimated_duration: float         # Typical duration in seconds
    execute: Callable                 # Async function to execute

class ActionRegistry:
    """Registry of available actions."""

    def __init__(self):
        self.actions: Dict[str, ActionDefinition] = {}

    def register(self, action: ActionDefinition):
        """Register an action."""
        self.actions[action.name] = action

    def get_action(self, name: str) -> ActionDefinition:
        """Get action by name."""
        return self.actions.get(name)

    def get_all_actions(self) -> List[ActionDefinition]:
        """Get all registered actions (for LLM prompting)."""
        return list(self.actions.values())
```

#### Initial Action Set

**1. speak(text: str, emotion: Optional[str] = None)**
- Uses existing SpeechAction/TTS
- Parameters:
  - `text`: What to say
  - `emotion`: Optional hint for tone (future use)
- Events: `action.speak.started`, `action.speak.completed`
- Conflicts: Other `speak` actions
- Duration: ~2-5 seconds

**2. update_display(section: str, content: str, style: Optional[dict] = None)**
- Updates TUI section with content and styling
- Parameters:
  - `section`: "status", "goal", "plan"
  - `content`: Text to display
  - `style`: {"color": "green", "bold": true}
- Events: `action.display.updated`
- Conflicts: None (updates merged)
- Duration: Instant

**3. focus_perception(modality: str)**
- Directs attention to perception input
- Parameters:
  - `modality`: "camera", "audio", "physical"
- Could adjust sampling rate or prioritize certain inputs
- Events: `action.perception.focused`
- Conflicts: None
- Duration: Instant

**4. adjust_volume(level: float)**
- Changes TTS volume
- Parameters:
  - `level`: 0.0 to 1.0
- Updates SpeechAction volume setting
- Events: `action.volume.adjusted`
- Conflicts: None
- Duration: Instant

**5. emit_sound(sound_type: str)**
- Plays non-speech sounds
- Parameters:
  - `sound_type`: "chime", "beep", "alert", "gentle_chime"
- Uses system beep or simple tone generation
- Events: `action.sound.emitted`
- Conflicts: Other `emit_sound` actions
- Duration: ~1 second

**6. wait(duration: float, condition: Optional[str] = None)**
- Pauses plan execution
- Parameters:
  - `duration`: Seconds to wait (max)
  - `condition`: Optional event to wait for (returns early if occurs)
- Conditions: "face_detected", "drive_threshold_crossed", or any event name
- Events: `action.wait.started`, `action.wait.completed`
- Conflicts: None (passive)
- Duration: Variable (up to duration param)

#### Extensibility Pattern

New actions register via decorator:

```python
from sociopsi.actions import register_action

@register_action(
    name="my_custom_action",
    description="Does something interesting",
    parameters={
        "param1": {"type": "string", "required": true},
        "param2": {"type": "number", "default": 1.0}
    },
    conflicts_with=["other_action"],
    estimated_duration=3.0
)
async def execute_my_action(param1: str, param2: float = 1.0):
    """Execute custom action."""
    # Do something
    # Publish events via event bus
    pass
```

Future actions could include:
- File operations (read, write, search)
- API calls (web requests, external services)
- Motor control (robotics, embodiment)
- Complex perception (object detection, face recognition)

## Integration with Existing Systems

### Drive System

- **Trigger**: Drives continue decaying naturally; when below threshold, trigger goal generation
- **Satisfaction**: Goal success can satisfy related drive (configurable per goal type)
- **Example**: Completing "seek social connection" satisfies affiliation by +0.3

### Archetypal Dialogue

Archetypes now participate in two types of dialogue:

1. **Contemplative dialogue** (existing): Generate internal thoughts every 10 seconds
2. **Goal dialogue** (new): Propose goals and plans when triggered by drives

Both use same archetypal personalities and LLM prompts. Ego mediates both with same harmony calculation.

### Memory System

- **Storage**: Goals, plans, and outcomes stored as memories
- **Intensity**: Based on outcome
  - Goal success: 0.8-1.0
  - Goal failure: 0.4-0.6
  - Partial success: 0.5-0.7
- **Retrieval**: Plans can query semantic memory: "What worked last time affiliation was low?"

### Meta-Cognition

- Meta-cognition can reflect on goal pursuit patterns
- Analyzes: success rate, common failures, drive-goal relationships
- Provides insights: "I notice I often fail to achieve nurturing goals"

### Event Bus

All new subsystems use existing event bus:

**New Event Types**:
- `goal.generated`, `goal.selected`, `goal.completed`, `goal.failed`, `goal.abandoned`
- `plan.created`, `plan.step_started`, `plan.step_completed`, `plan.revised`
- `action.{name}.started`, `action.{name}.completed`, `action.{name}.failed`

### TUI

TUI displays goal/plan state in real-time:
- Active goals with priorities
- Current plan being executed
- Recent goal completions/failures

### Agent Main Loop

```python
async def update(self):
    """Agent update cycle."""
    current_time = time.time()
    dt = current_time - self.last_update_time

    # Existing systems
    self.drive_system.update(dt, physical_state)
    self.memory_system.update(dt)
    # ... perception, dialogue, meta-cognition ...

    # NEW: Goal system
    await self.goal_manager.update(dt)

    # NEW: Action executor
    await self.action_executor.update(dt)
```

## Implementation Plan

### Task 1: Action Registry & Basic Actions
- Create `actions/registry.py` with ActionRegistry
- Create `actions/action_types.py` with ActionDefinition
- Implement initial 6 actions (speak, update_display, focus_perception, adjust_volume, emit_sound, wait)
- Add action decorator for extensibility
- Tests: Action registration, parameter validation, conflict detection

### Task 2: Goal System
- Create `subsystems/goals/goal.py` with Goal and GoalStatus
- Create `subsystems/goals/manager.py` with GoalManager
- Implement goal generation via archetypal proposals
- Implement Ego selection and priority assignment
- Implement success criteria checking
- Tests: Goal creation, selection, criteria evaluation, lifecycle

### Task 3: Action Planner
- Create `subsystems/planning/planner.py` with ActionPlanner
- Create `subsystems/planning/action_plan.py` with ActionPlan and ActionStep
- Implement archetypal plan proposals
- Implement Ego plan synthesis
- Implement plan validation
- Tests: Plan generation, synthesis, validation, fallbacks

### Task 4: Action Executor
- Create `subsystems/execution/executor.py` with ActionExecutor
- Implement execution loop with monitoring
- Implement early success detection
- Implement blocking detection and re-planning
- Implement parallel execution with conflict resolution
- Tests: Step execution, monitoring, re-planning, parallel goals

### Task 5: Agent Integration
- Integrate GoalManager into SocioPsiAgent
- Integrate ActionExecutor into agent update loop
- Connect goal generation to drive threshold events
- Update TUI to display goals and plans
- Tests: End-to-end goal pursuit, drive satisfaction, multiple goals

### Task 6: Enhanced TUI
- Add goal status panel showing active goals
- Add plan execution panel showing current steps
- Add goal history panel showing recent completions/failures
- Color-coded priority and status indicators

### Task 7: Configuration
- Add goal system config to config.toml
- Add action config (timeouts, retry limits)
- Add planning config (max plan length, re-plan limits)

### Task 8: Testing & Documentation
- Comprehensive integration tests
- End-to-end scenarios (low drive → goal → plan → execution → success)
- Update README with goal system examples
- Update STATUS with Phase 4 capabilities

## Testing Strategy

### Unit Tests

**Goal System** (~12 tests):
- Goal creation and initialization
- Goal status transitions
- Success criteria evaluation (baseline, specific, timeout)
- GoalManager queue management
- Archetypal goal proposals
- Ego goal selection

**Action Planner** (~10 tests):
- Archetypal plan proposals
- Ego plan synthesis
- Plan validation (actions exist, params valid, length)
- Re-planning with failure context
- Fallback plan generation

**Action Executor** (~15 tests):
- Step execution
- Early success detection
- Blocking detection
- Re-planning triggers
- Parallel execution
- Conflict detection and resolution
- Goal completion/failure handling

**Action Registry** (~8 tests):
- Action registration
- Parameter validation
- Conflict rule enforcement
- Action retrieval
- Each action's execution

### Integration Tests

**End-to-End** (~8 tests):
- Low drive → goal generation → planning → execution → success
- Goal failure → re-planning → eventual success
- Multiple goals → parallel execution
- Goal timeout → abandonment
- Early success → skip remaining steps

### Mock Strategy

- Mock LLM responses for predictable testing
- Mock action execution for controlled outcomes
- Mock event bus for event verification
- Example: Shadow always suggests aggressive goals, verify Ego balances

## Error Handling

### LLM Failures

- **Timeout on goal generation**: Fall back to simple goal ("satisfy [drive_name]")
- **Invalid LLM response**: Log, retry once, then use fallback
- **Complete LLM unavailability**: Agent continues contemplative dialogue but doesn't pursue new goals

### Action Failures

- **Action error**: Mark step as failed, trigger re-planning
- **Re-planning fails**: Abandon goal, log to memory
- **Critical action unavailable** (e.g., TTS init fails): Mark action as unavailable, plans won't include it

### Goal Conflicts

- **Multiple high-priority goals**: Archetypal consensus decides order
- **Deadlock** (all actions conflict): Execute highest priority, queue others
- **Goal timeout**: Abandon gracefully, publish event

### Memory & Logging

- All errors logged to semantic memory with medium-high intensity
- Agent can reflect on past failures in meta-cognition
- Failures inform future goal/plan generation ("Last time I tried X, Y happened")

## Success Criteria

Phase 4 is complete when:

1. ✅ Agent generates goals when drives fall below threshold
2. ✅ Archetypes propose different goals reflecting their personalities
3. ✅ Ego selects and prioritizes goals via archetypal consensus
4. ✅ Archetypes propose different action plans for goals
5. ✅ Ego synthesizes competing plans into coherent plans
6. ✅ Executor runs plans with continuous monitoring
7. ✅ Early success detection skips remaining steps
8. ✅ Re-planning occurs when actions fail
9. ✅ Multiple non-conflicting goals execute in parallel
10. ✅ All 6 initial actions implemented and working
11. ✅ TUI displays goal/plan state in real-time
12. ✅ All tests passing (target: 150+ tests total)
13. ✅ Documentation updated

## Future Enhancements (Phase 5+)

- **Learning from experience**: Goals/plans that succeed become more likely in future
- **User interaction**: Accept natural language commands as goals
- **Complex actions**: Multi-step composite actions, conditional actions
- **Goal decomposition**: Break complex goals into sub-goals
- **Emotional modulation**: Harmony level affects goal selection and planning style
- **Embodied actions**: If robotics added, actions for movement, manipulation, etc.

## Timeline Estimate

- Task 1 (Actions): ~2-3 hours
- Task 2 (Goals): ~3-4 hours
- Task 3 (Planner): ~3-4 hours
- Task 4 (Executor): ~4-5 hours
- Task 5 (Integration): ~2-3 hours
- Task 6 (TUI): ~1-2 hours
- Task 7 (Config): ~1 hour
- Task 8 (Testing): ~2-3 hours

**Total**: ~18-25 hours of development

## Notes

- This phase significantly increases LLM usage (goal proposals + plan proposals per low drive)
- Consider caching common goals/plans if performance becomes issue
- Action system designed for future extensibility (file ops, APIs, robotics)
- Parallel execution is complex but essential for realistic multi-goal behavior
- Early success detection prevents unnecessary actions (efficient goal pursuit)

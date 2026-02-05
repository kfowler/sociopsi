"""Goal manager for managing agent goals."""

from typing import Any

from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.archetypes.base import Archetype
from sociopsi.subsystems.archetypes.ego import Ego
from sociopsi.subsystems.drives import DriveSystem
from sociopsi.subsystems.goals.goal import Goal


class GoalManager:
    """Manages agent goals throughout their lifecycle.

    The manager generates goals when drives fall below threshold, tracks active
    and pending goals, evaluates success criteria, and handles goal completion.
    """

    def __init__(
        self,
        event_bus: EventBus,
        llm_client: OllamaClient,
        drive_system: DriveSystem,
        max_active_goals: int = 3,
        max_pending_goals: int = 5,
        max_history: int = 20,
    ) -> None:
        """Initialize goal manager.

        Args:
            event_bus: Event bus for publishing goal events
            llm_client: LLM client for goal generation
            drive_system: Drive system to monitor
            max_active_goals: Maximum concurrent active goals
            max_pending_goals: Maximum pending goals in queue
            max_history: Maximum completed goals to keep in history
        """
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.drive_system = drive_system
        self.max_active_goals = max_active_goals
        self.max_pending_goals = max_pending_goals
        self.max_history = max_history

        self.active_goals: list[Goal] = []
        self.pending_goals: list[Goal] = []
        self.completed_goals: list[Goal] = []  # Recent history

        # Archetypes will be set later during integration
        self.archetypes: dict[str, Archetype] = {}
        self.ego: Ego | None = None

    def set_archetypes(self, archetypes: dict[str, Archetype], ego: Ego) -> None:
        """Set archetype and ego references for goal generation.

        Args:
            archetypes: Dictionary of archetype instances
            ego: Ego instance
        """
        self.archetypes = archetypes
        self.ego = ego

    async def generate_goals(self, low_drives: list[str]) -> list[Goal]:
        """Generate goals for low drives via archetypal proposals.

        Args:
            low_drives: List of drive names below threshold

        Returns:
            List of generated goals
        """
        if not self.archetypes or not self.ego:
            # Can't generate goals without archetypes
            return []

        goals = []

        for drive_name in low_drives:
            # Get archetypal goal proposals
            proposals = await self._get_archetypal_proposals(drive_name)

            if not proposals:
                continue

            # Ego selects goals from proposals
            selected_goals = await self._ego_select_goals(drive_name, proposals)

            for goal in selected_goals:
                self.add_goal(goal)
                goals.append(goal)

        return goals

    async def _get_archetypal_proposals(self, drive_name: str) -> list[dict[str, str]]:
        """Get goal proposals from each archetype.

        Args:
            drive_name: Drive that is low

        Returns:
            List of proposals, each with archetype name and goal description
        """
        proposals = []
        drive_state = self.drive_system.get_state()
        drive_value = drive_state[drive_name]["value"]

        for archetype_name, archetype in self.archetypes.items():
            # Build prompt for archetype to propose goal
            prompt = f"""Your {drive_name} drive is low (current value: {drive_value:.2f}).

As the {archetype_name} archetype, propose a specific, achievable goal to address this need.
The goal should:
- Be concrete and actionable
- Reflect your archetypal personality
- Be achievable through available actions (speaking, updating display, focusing perception)
- Be 1-2 sentences

Propose a goal:"""

            try:
                response = await self.llm_client.generate(
                    prompt, temperature=archetype.get_temperature(), max_tokens=100
                )

                goal_description = response.strip()

                proposals.append(
                    {
                        "archetype": archetype_name,
                        "description": goal_description,
                    }
                )

            except Exception as e:
                print(f"Warning: Failed to get goal proposal from {archetype_name}: {e}")
                continue

        return proposals

    async def _ego_select_goals(
        self, drive_name: str, proposals: list[dict[str, str]]
    ) -> list[Goal]:
        """Ego selects and prioritizes goals from archetypal proposals.

        Args:
            drive_name: Drive that is low
            proposals: Archetypal goal proposals

        Returns:
            List of selected goals with priorities
        """
        if not proposals:
            return []

        # Build prompt for Ego to select and prioritize
        proposals_text = "\n".join(
            f"{i + 1}. {p['archetype']}: {p['description']}" for i, p in enumerate(proposals)
        )

        drive_state = self.drive_system.get_state()
        drive_value = drive_state[drive_name]["value"]

        prompt = f"""You are the Ego, selecting goals to pursue based on archetypal proposals.

Drive: {drive_name} (value: {drive_value:.2f})

Archetypal proposals:
{proposals_text}

Consider:
1. Urgency (how low is the drive?)
2. Feasibility (can this realistically be achieved?)
3. Harmony (does this fit current psychological integration?)

Select 1-2 goals to pursue. For each, provide:
- The number of the proposal
- Priority (0.0 to 1.0, where 1.0 is highest)

Format your response as:
GOAL: <number> PRIORITY: <value>

Example:
GOAL: 1 PRIORITY: 0.8
GOAL: 3 PRIORITY: 0.5"""

        try:
            response = await self.llm_client.generate(prompt, temperature=0.6, max_tokens=150)

            # Parse Ego's selection
            selected_goals = self._parse_ego_selection(drive_name, proposals, response)
            return selected_goals

        except Exception as e:
            print(f"Warning: Ego goal selection failed: {e}")
            # Fallback: Select first proposal with medium priority
            if proposals:
                return [
                    Goal(
                        description=proposals[0]["description"],
                        related_drive=drive_name,
                        priority=0.5,
                        proposing_archetype=proposals[0]["archetype"],
                        success_criteria=self._get_default_success_criteria(drive_name),
                    )
                ]
            return []

    def _parse_ego_selection(
        self, drive_name: str, proposals: list[dict[str, str]], response: str
    ) -> list[Goal]:
        """Parse Ego's goal selection response.

        Args:
            drive_name: Drive name
            proposals: Original proposals
            response: LLM response

        Returns:
            List of selected goals
        """
        goals = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            if not line.startswith("GOAL:"):
                continue

            try:
                # Parse "GOAL: 1 PRIORITY: 0.8"
                parts = line.split("PRIORITY:")
                goal_part = parts[0].replace("GOAL:", "").strip()
                priority_part = parts[1].strip() if len(parts) > 1 else "0.5"

                goal_num = int(goal_part) - 1  # Convert to 0-indexed
                priority = float(priority_part)

                if 0 <= goal_num < len(proposals):
                    proposal = proposals[goal_num]
                    goal = Goal(
                        description=proposal["description"],
                        related_drive=drive_name,
                        priority=min(1.0, max(0.0, priority)),  # Clamp to [0, 1]
                        proposing_archetype=proposal["archetype"],
                        success_criteria=self._get_default_success_criteria(drive_name),
                    )
                    goals.append(goal)

            except (ValueError, IndexError) as e:
                print(f"Warning: Failed to parse goal selection line: {line} ({e})")
                continue

        return goals

    def _get_default_success_criteria(self, drive_name: str) -> dict[str, Any]:
        """Get default success criteria for a drive.

        Args:
            drive_name: Drive name

        Returns:
            Success criteria dict
        """
        return {
            "baseline": {
                "drive": drive_name,
                "threshold": 0.6,  # Drive must reach 0.6 to succeed
            },
            "specific": [],
            "timeout": 60.0,  # 60 second timeout
        }

    def add_goal(self, goal: Goal) -> None:
        """Add goal to pending queue.

        Args:
            goal: Goal to add
        """
        # Don't add if queue is full
        if len(self.pending_goals) >= self.max_pending_goals:
            return

        self.pending_goals.append(goal)

        # Publish event
        self.event_bus.publish(
            "goal.generated",
            {
                "goal_id": goal.id,
                "description": goal.description,
                "related_drive": goal.related_drive,
                "priority": goal.priority,
            },
        )

    def activate_goal(self, goal_id: str) -> bool:
        """Move goal from pending to active.

        Args:
            goal_id: Goal ID

        Returns:
            True if activated
        """
        # Find goal in pending
        goal = None
        for i, g in enumerate(self.pending_goals):
            if g.id == goal_id:
                goal = self.pending_goals.pop(i)
                break

        if not goal:
            return False

        # Don't activate if at max active goals
        if len(self.active_goals) >= self.max_active_goals:
            self.pending_goals.insert(0, goal)  # Put back at front
            return False

        # Activate goal
        goal.activate()
        self.active_goals.append(goal)

        # Publish event
        self.event_bus.publish(
            "goal.selected",
            {
                "goal_id": goal.id,
                "description": goal.description,
                "related_drive": goal.related_drive,
                "priority": goal.priority,
            },
        )

        return True

    def complete_goal(self, goal_id: str, success: bool) -> None:
        """Mark goal as completed or failed.

        Args:
            goal_id: Goal ID
            success: True if goal succeeded
        """
        # Find goal in active
        goal = None
        for i, g in enumerate(self.active_goals):
            if g.id == goal_id:
                goal = self.active_goals.pop(i)
                break

        if not goal:
            return

        # Complete goal
        goal.complete(success=success)

        # Add to history
        self.completed_goals.append(goal)
        if len(self.completed_goals) > self.max_history:
            self.completed_goals.pop(0)

        # Publish event
        event_name = "goal.completed" if success else "goal.failed"
        self.event_bus.publish(
            event_name,
            {
                "goal_id": goal.id,
                "description": goal.description,
                "related_drive": goal.related_drive,
                "elapsed_time": goal.get_elapsed_time(),
            },
        )

    def abandon_goal(self, goal_id: str) -> None:
        """Abandon a goal (timeout or priority shift).

        Args:
            goal_id: Goal ID
        """
        # Find goal in active
        goal = None
        for i, g in enumerate(self.active_goals):
            if g.id == goal_id:
                goal = self.active_goals.pop(i)
                break

        if not goal:
            return

        # Abandon goal
        goal.abandon()

        # Add to history
        self.completed_goals.append(goal)
        if len(self.completed_goals) > self.max_history:
            self.completed_goals.pop(0)

        # Publish event
        self.event_bus.publish(
            "goal.abandoned",
            {
                "goal_id": goal.id,
                "description": goal.description,
                "related_drive": goal.related_drive,
                "elapsed_time": goal.get_elapsed_time(),
            },
        )

    def check_success_criteria(self, goal: Goal) -> bool:
        """Check if goal's success criteria are met.

        Args:
            goal: Goal to check

        Returns:
            True if success criteria met
        """
        criteria = goal.success_criteria

        # Check baseline (drive threshold)
        baseline = criteria.get("baseline", {})
        if baseline:
            drive_name = baseline.get("drive")
            threshold = baseline.get("threshold", 0.6)

            if drive_name:
                drive_state = self.drive_system.get_state()
                if drive_name in drive_state:
                    drive_value = drive_state[drive_name]["value"]
                    if drive_value < threshold:
                        return False  # Drive still below threshold

        # TODO: Check specific criteria (events, actions completed)
        # For now, just check baseline

        return True

    def get_active_goals(self) -> list[Goal]:
        """Get list of active goals.

        Returns:
            List of active goals, sorted by priority (highest first)
        """
        return sorted(self.active_goals, key=lambda g: g.priority, reverse=True)

    def get_pending_goals(self) -> list[Goal]:
        """Get list of pending goals.

        Returns:
            List of pending goals, sorted by priority
        """
        return sorted(self.pending_goals, key=lambda g: g.priority, reverse=True)

    def get_state(self) -> dict[str, Any]:
        """Get goal manager state.

        Returns:
            State dictionary
        """
        return {
            "active_count": len(self.active_goals),
            "pending_count": len(self.pending_goals),
            "completed_count": len(self.completed_goals),
            "active_goals": [g.to_dict() for g in self.get_active_goals()],
            "pending_goals": [g.to_dict() for g in self.get_pending_goals()],
        }

    async def update(self, dt: float) -> None:
        """Update goal system (check timeouts, etc.).

        Args:
            dt: Delta time since last update
        """
        # Check active goals for timeout
        for goal in list(self.active_goals):  # Copy to allow modification
            if goal.check_timeout():
                self.abandon_goal(goal.id)

        # Activate pending goals if space available
        if len(self.active_goals) < self.max_active_goals:
            pending = self.get_pending_goals()
            if pending:
                # Activate highest priority pending goal
                self.activate_goal(pending[0].id)

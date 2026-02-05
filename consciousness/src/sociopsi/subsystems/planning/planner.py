"""Action planner - generates plans via archetypal synthesis."""

import time
from typing import Any

from sociopsi.actions.registry import ActionRegistry
from sociopsi.core.event_bus import EventBus
from sociopsi.llm.ollama_client import OllamaClient
from sociopsi.subsystems.archetypes.base import Archetype
from sociopsi.subsystems.archetypes.ego import Ego
from sociopsi.subsystems.goals.goal import Goal
from sociopsi.subsystems.planning.action_plan import ActionPlan, ActionStep


class ActionPlanner:
    """Generates action plans for goals via archetypal synthesis."""

    def __init__(
        self,
        event_bus: EventBus,
        llm_client: OllamaClient,
        action_registry: ActionRegistry,
    ) -> None:
        """Initialize action planner.

        Args:
            event_bus: Event bus for publishing plan events
            llm_client: LLM client for plan generation
            action_registry: Registry of available actions
        """
        self.event_bus = event_bus
        self.llm_client = llm_client
        self.action_registry = action_registry
        self.archetypes: dict[str, Archetype] = {}
        self.ego: Ego | None = None
        self.max_plan_length = 10

    def set_archetypes(self, archetypes: dict[str, Archetype], ego: Ego) -> None:
        """Set archetype and ego references.

        Args:
            archetypes: Dictionary of archetype instances
            ego: Ego instance
        """
        self.archetypes = archetypes
        self.ego = ego

    async def create_plan(self, goal: Goal) -> ActionPlan | None:
        """Create action plan for goal via archetypal synthesis.

        Args:
            goal: Goal to create plan for

        Returns:
            Action plan or None if planning failed
        """
        if not self.archetypes or not self.ego:
            return None

        # Get archetypal plan proposals
        archetypal_plans = await self._get_archetypal_plans(goal)

        if not archetypal_plans:
            return await self._create_fallback_plan(goal)

        # Ego synthesizes plans
        synthesized_plan = await self._synthesize_plan(goal, archetypal_plans)

        if not synthesized_plan or not self._validate_plan(synthesized_plan):
            return await self._create_fallback_plan(goal)

        return synthesized_plan

    async def _get_archetypal_plans(self, goal: Goal) -> list[dict[str, Any]]:
        """Get action plan proposals from archetypes.

        Args:
            goal: Goal to plan for

        Returns:
            List of archetypal plan proposals
        """
        proposals = []
        actions_summary = self.action_registry.get_actions_summary()

        for archetype_name, archetype in self.archetypes.items():
            prompt = f"""Goal: {goal.description}

{actions_summary}

As the {archetype_name} archetype, propose a sequence of 2-5 actions to achieve this goal.
Use the format:
1. action_name(param1="value", param2=123)
2. action_name(param="value")

Example:
1. focus_perception(modality="camera")
2. speak(text="Hello!")
3. wait(duration=2)

Your plan:"""

            try:
                response = await self.llm_client.generate(
                    prompt, temperature=archetype.get_temperature(), max_tokens=200
                )

                steps = self._parse_plan_response(response)
                if steps:
                    proposals.append(
                        {
                            "archetype": archetype_name,
                            "steps": steps,
                        }
                    )

            except Exception as e:
                print(f"Warning: Failed to get plan from {archetype_name}: {e}")
                continue

        return proposals

    def _parse_plan_response(self, response: str) -> list[dict[str, Any]]:
        """Parse LLM plan response into action steps.

        Args:
            response: LLM response

        Returns:
            List of action steps
        """
        steps = []
        lines = response.split("\n")

        for line in lines:
            line = line.strip()
            if not line or not any(char.isdigit() for char in line[:3]):
                continue

            # Simple parsing: extract action_name(params)
            try:
                # Remove numbering
                if ". " in line:
                    line = line.split(". ", 1)[1]

                # Extract action name
                if "(" in line:
                    action_name = line.split("(")[0].strip()
                    params_str = line.split("(", 1)[1].rsplit(")", 1)[0]

                    # Parse parameters (simple key=value parsing)
                    parameters = {}
                    if params_str.strip():
                        for param in params_str.split(","):
                            if "=" in param:
                                key, value = param.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip("\"'")

                                # Try to convert to number
                                try:
                                    value = float(value)
                                    if value.is_integer():
                                        value = int(value)
                                except ValueError:
                                    pass

                                parameters[key] = value

                    steps.append(
                        {
                            "action_name": action_name,
                            "parameters": parameters,
                        }
                    )

            except Exception as e:
                print(f"Warning: Failed to parse plan line: {line} ({e})")
                continue

        return steps[: self.max_plan_length]

    async def _synthesize_plan(
        self, goal: Goal, archetypal_plans: list[dict[str, Any]]
    ) -> ActionPlan | None:
        """Ego synthesizes archetypal plans into unified plan.

        Args:
            goal: Goal being planned for
            archetypal_plans: Plans from each archetype

        Returns:
            Synthesized action plan
        """
        # Build prompt for Ego
        plans_text = ""
        for i, plan_data in enumerate(archetypal_plans, 1):
            steps_text = "\n".join(
                f"  {j}. {step['action_name']}({', '.join(f'{k}={v}' for k, v in step['parameters'].items())})"
                for j, step in enumerate(plan_data["steps"], 1)
            )
            plans_text += f"\n{plan_data['archetype']}:\n{steps_text}\n"

        actions_summary = self.action_registry.get_actions_summary()

        prompt = f"""Goal: {goal.description}

{actions_summary}

Archetypal plans:
{plans_text}

As Ego, synthesize these into one coherent 2-5 step plan.
Balance the perspectives, taking the best ideas from each.

Format:
1. action_name(param="value")
2. action_name(param=value)

Your synthesized plan:"""

        try:
            response = await self.llm_client.generate(prompt, temperature=0.6, max_tokens=200)

            steps_data = self._parse_plan_response(response)

            if not steps_data:
                return None

            # Convert to ActionSteps
            steps = []
            for step_data in steps_data:
                steps.append(
                    ActionStep(
                        action_name=step_data["action_name"],
                        parameters=step_data["parameters"],
                    )
                )

            plan = ActionPlan(
                goal_id=goal.id,
                steps=steps,
                created_at=time.time(),
            )

            self.event_bus.publish(
                "plan.created",
                {
                    "goal_id": goal.id,
                    "step_count": len(steps),
                },
            )

            return plan

        except Exception as e:
            print(f"Warning: Ego plan synthesis failed: {e}")
            return None

    def _validate_plan(self, plan: ActionPlan) -> bool:
        """Validate action plan.

        Args:
            plan: Plan to validate

        Returns:
            True if valid
        """
        if not plan.steps:
            return False

        if len(plan.steps) > self.max_plan_length:
            return False

        # Check all actions exist
        for step in plan.steps:
            if not self.action_registry.has_action(step.action_name):
                return False

            # Validate parameters
            action = self.action_registry.get_action(step.action_name)
            if action:
                valid, error = action.validate_parameters(step.parameters)
                if not valid:
                    print(f"Warning: Invalid parameters for {step.action_name}: {error}")
                    return False

        return True

    async def _create_fallback_plan(self, goal: Goal) -> ActionPlan:
        """Create simple fallback plan.

        Args:
            goal: Goal to plan for

        Returns:
            Fallback plan
        """
        # Simple fallback: speak about the goal
        steps = [
            ActionStep(
                action_name="speak",
                parameters={"text": f"Working on: {goal.description}"},
            )
        ]

        return ActionPlan(
            goal_id=goal.id,
            steps=steps,
            created_at=time.time(),
        )

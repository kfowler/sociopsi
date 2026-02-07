"""Expectation Horizon - predictive forward model for anticipatory processing.

Implements a forward model that predicts drive state changes from proposed
actions, enabling impulse inhibition and consequence simulation.

Uses SATISFACTION_MAP from drives.py as the basis for predictions. Each
action's expected drive effects are already encoded there. The model
simulates N-step lookahead by predicting cumulative drive changes across
an action sequence, then suppresses actions whose predicted net outcome
is harmful or wasteful.

Counterfactual learning compares predicted vs actual drive changes after
execution, adjusting correction factors over time.

Reference: Bach 2015 Modeling Motivation, Section on anticipatory processing.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from sociopsi.drives import SATISFACTION_MAP, Drive, DriveSystem
from sociopsi.types import Action


@dataclass
class PredictedDriveChange:
    """Predicted change to a single drive from an action."""

    drive_name: str
    predicted_satisfaction: float
    urgency_weight: float
    weighted_benefit: float  # satisfaction * urgency_weight


@dataclass
class ActionExpectation:
    """Expected outcome of executing a single action."""

    action: Action
    drive_changes: list[PredictedDriveChange]
    net_valence: float  # positive = beneficial, negative = harmful/wasteful
    confidence: float  # 0-1, how reliable the prediction is


@dataclass
class HorizonResult:
    """Result of evaluating a proposed action sequence."""

    expectations: list[ActionExpectation]
    suppressed: list[Action]
    approved: list[Action]
    total_valence: float


class ExpectationHorizon:
    """Forward model predicting drive state changes from proposed actions.

    The model uses SATISFACTION_MAP as its basis: each action's expected
    drive satisfaction values are already encoded there. For callable
    satisfaction values (which depend on action results), the model uses
    a conservative estimate (empty result dict).

    Impulse inhibition: actions whose predicted net valence falls below
    the suppression threshold are flagged and removed from the sequence.

    N-step lookahead: when evaluating a sequence, the model simulates
    cumulative drive changes so that redundant actions show diminishing
    returns (since earlier actions in the sequence already partially
    satisfy the same drives).

    Counterfactual learning: after action execution, predicted vs actual
    drive changes are compared and correction factors are adjusted.
    """

    def __init__(
        self,
        suppression_threshold: float = -0.05,
        learning_rate: float = 0.1,
    ) -> None:
        self.suppression_threshold = suppression_threshold
        self.learning_rate = learning_rate
        # Correction factors learned from counterfactual comparison.
        # Maps (action_type, drive_name) -> multiplier applied to predicted satisfaction.
        self._corrections: dict[tuple[str, str], float] = {}

    def predict_action(
        self,
        action: Action,
        drives: dict[str, Drive],
    ) -> ActionExpectation:
        """Predict drive state changes from a single action.

        For each drive affected by the action (per SATISFACTION_MAP), compute:
        - predicted_satisfaction: the satisfaction value (with corrections)
        - urgency_weight: how urgently the drive needs attention
        - weighted_benefit: satisfaction * urgency_weight

        The net valence is the sum of weighted benefits. A positive valence
        means the action is expected to help; near-zero means neutral; negative
        is unlikely from SATISFACTION_MAP alone but can arise from corrections.

        Args:
            action: The proposed action.
            drives: Current drive states (name -> Drive).

        Returns:
            ActionExpectation with predicted changes and net valence.
        """
        changes: list[PredictedDriveChange] = []

        sat_map = SATISFACTION_MAP.get(action.type, {})
        for drive_name, sat_value in sat_map.items():
            if drive_name not in drives:
                continue

            drive = drives[drive_name]

            # Get base satisfaction prediction
            if callable(sat_value):
                predicted_sat = sat_value({})
            else:
                predicted_sat = sat_value

            # Apply learned correction
            correction_key = (action.type, drive_name)
            if correction_key in self._corrections:
                predicted_sat *= self._corrections[correction_key]

            # Clamp to valid range
            predicted_sat = max(0.0, min(1.0, predicted_sat))

            # Weight by urgency: satisfying urgent drives is more valuable
            urgency_weight = drive.urgency if drive.urgency > 0.01 else drive.demand
            weighted_benefit = predicted_sat * urgency_weight

            changes.append(
                PredictedDriveChange(
                    drive_name=drive_name,
                    predicted_satisfaction=predicted_sat,
                    urgency_weight=urgency_weight,
                    weighted_benefit=weighted_benefit,
                )
            )

        net_valence = sum(c.weighted_benefit for c in changes)

        # Confidence: base 0.5 from SATISFACTION_MAP, higher with learned corrections
        corrections_for_action = sum(
            1 for dn in sat_map if (action.type, dn) in self._corrections
        )
        confidence = min(0.9, 0.5 + 0.1 * corrections_for_action)

        return ActionExpectation(
            action=action,
            drive_changes=changes,
            net_valence=net_valence,
            confidence=confidence,
        )

    def evaluate(
        self,
        actions: list[Action],
        drive_system: DriveSystem,
    ) -> HorizonResult:
        """Evaluate a sequence of proposed actions with N-step lookahead.

        Simulates cumulative drive changes across the sequence. Each action
        is evaluated against the simulated drive state (which incorporates
        effects of prior actions in the sequence). This means redundant
        actions naturally show diminishing returns.

        Actions with net valence below the suppression threshold are
        suppressed (impulse inhibition).

        Args:
            actions: Proposed action sequence.
            drive_system: Current drive system state.

        Returns:
            HorizonResult with approved/suppressed actions and expectations.
        """
        expectations: list[ActionExpectation] = []
        approved: list[Action] = []
        suppressed: list[Action] = []

        # Deep copy drives for simulation so we don't mutate the real state
        sim_drives: dict[str, Drive] = {
            name: deepcopy(drive) for name, drive in drive_system.drives.items()
        }

        for action in actions:
            expectation = self.predict_action(action, sim_drives)
            expectations.append(expectation)

            if expectation.net_valence < self.suppression_threshold:
                suppressed.append(action)
            else:
                approved.append(action)
                # Update simulated drives to reflect this action's predicted effect.
                # Apply predicted satisfaction so subsequent actions see diminished need.
                for change in expectation.drive_changes:
                    if change.drive_name in sim_drives:
                        sim_drives[change.drive_name].satisfy(change.predicted_satisfaction)

        total_valence = sum(e.net_valence for e in expectations)

        return HorizonResult(
            expectations=expectations,
            suppressed=suppressed,
            approved=approved,
            total_valence=total_valence,
        )

    def snapshot_drives(self, drive_system: DriveSystem) -> dict[str, float]:
        """Capture current drive demands for later counterfactual comparison.

        Args:
            drive_system: Current drive system state.

        Returns:
            Dictionary mapping drive names to their current demand values.
        """
        return {name: drive.demand for name, drive in drive_system.drives.items()}

    def learn_from_outcome(
        self,
        expectations: list[ActionExpectation],
        drives_before: dict[str, float],
        drives_after: dict[str, float],
    ) -> None:
        """Update forward model from observed outcomes (counterfactual learning).

        Compares predicted satisfaction effects with actual drive demand changes.
        Adjusts correction factors so future predictions are more accurate.

        Args:
            expectations: The predictions made before execution.
            drives_before: Drive demands snapshot before action execution.
            drives_after: Drive demands snapshot after action execution.
        """
        for expectation in expectations:
            action_type = expectation.action.type
            for change in expectation.drive_changes:
                dn = change.drive_name
                if dn not in drives_before or dn not in drives_after:
                    continue

                actual_delta = drives_after[dn] - drives_before[dn]
                # We predicted satisfaction -> demand reduction.
                # Expected delta is approximately: -predicted_satisfaction * fall_rate * dt
                # But since we don't know exact dt, we compare directions and magnitudes.
                predicted_sat = change.predicted_satisfaction

                if predicted_sat < 1e-6:
                    continue

                correction_key = (action_type, dn)
                current = self._corrections.get(correction_key, 1.0)

                # If actual demand dropped more than expected, increase correction.
                # If demand dropped less (or rose), decrease correction.
                # We use the sign of actual_delta: negative = good (demand dropped).
                if actual_delta < 0:
                    # Drive improved — nudge correction up if we underestimated
                    adjustment = 1.0 + abs(actual_delta) / predicted_sat
                else:
                    # Drive worsened or stayed same — nudge correction down
                    adjustment = max(0.1, 1.0 - actual_delta / predicted_sat)

                updated = current + self.learning_rate * (adjustment - current)
                self._corrections[correction_key] = max(0.1, min(3.0, updated))

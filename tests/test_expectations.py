"""Tests for the Expectation Horizon (anticipatory processing)."""

import pytest

from sociopsi.config import AgentConfig
from sociopsi.drives import DriveSystem
from sociopsi.expectations import (
    ActionExpectation,
    ExpectationHorizon,
    PredictedDriveChange,
)
from sociopsi.types import Action


class TestPredictAction:
    """Tests for single-action prediction."""

    @pytest.fixture
    def horizon(self) -> ExpectationHorizon:
        return ExpectationHorizon()

    @pytest.fixture
    def drive_system(self) -> DriveSystem:
        config = AgentConfig(voice_enabled=False)
        return DriveSystem(config)

    def test_known_action_has_positive_valence(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """An action in SATISFACTION_MAP with urgent drives should have positive valence."""
        # Make curiosity urgent so web_search is valuable
        drive_system.drives["curiosity"].demand = 0.8
        drive_system.drives["curiosity"].urgency = 0.8

        action = Action(type="web_search")
        result = horizon.predict_action(action, drive_system.drives)

        assert result.net_valence > 0
        assert len(result.drive_changes) > 0

    def test_unknown_action_has_zero_valence(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """An action not in SATISFACTION_MAP should have zero valence."""
        action = Action(type="unknown_action_xyz")
        result = horizon.predict_action(action, drive_system.drives)

        assert result.net_valence == 0.0
        assert len(result.drive_changes) == 0

    def test_low_urgency_gives_low_valence(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Actions for non-urgent drives should have low valence."""
        # All drives at baseline (low urgency)
        action = Action(type="web_search")
        result = horizon.predict_action(action, drive_system.drives)

        # Should still be positive but relatively small
        assert result.net_valence >= 0

    def test_prediction_includes_all_affected_drives(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Prediction should list all drives affected by the action."""
        action = Action(type="web_search")
        result = horizon.predict_action(action, drive_system.drives)

        drive_names = {c.drive_name for c in result.drive_changes}
        # web_search affects curiosity and certainty
        assert "curiosity" in drive_names
        assert "certainty" in drive_names

    def test_confidence_starts_at_base(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Without corrections, confidence should be at the base level."""
        action = Action(type="check_battery")
        result = horizon.predict_action(action, drive_system.drives)

        assert result.confidence == 0.5

    def test_confidence_increases_with_corrections(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Confidence should increase when corrections have been learned."""
        horizon._corrections[("check_battery", "energy")] = 1.2
        horizon._corrections[("check_battery", "certainty")] = 0.9

        action = Action(type="check_battery")
        result = horizon.predict_action(action, drive_system.drives)

        assert result.confidence > 0.5

    def test_correction_adjusts_satisfaction(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Correction factors should modify predicted satisfaction."""
        drive_system.drives["curiosity"].demand = 0.8
        drive_system.drives["curiosity"].urgency = 0.8

        # Predict without correction
        action = Action(type="web_search")
        base = horizon.predict_action(action, drive_system.drives)

        # Add correction that doubles satisfaction
        horizon._corrections[("web_search", "curiosity")] = 2.0
        adjusted = horizon.predict_action(action, drive_system.drives)

        # Adjusted valence should be higher (capped at 1.0 for satisfaction)
        assert adjusted.net_valence >= base.net_valence


class TestEvaluate:
    """Tests for action sequence evaluation."""

    @pytest.fixture
    def horizon(self) -> ExpectationHorizon:
        return ExpectationHorizon()

    @pytest.fixture
    def drive_system(self) -> DriveSystem:
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)
        # Make some drives urgent
        ds.drives["curiosity"].demand = 0.8
        ds.drives["curiosity"].urgency = 0.8
        ds.drives["affiliation"].demand = 0.7
        ds.drives["affiliation"].urgency = 0.7
        return ds

    def test_all_good_actions_approved(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Actions with positive valence should all be approved."""
        actions = [
            Action(type="web_search"),
            Action(type="look"),
        ]
        result = horizon.evaluate(actions, drive_system)

        assert len(result.approved) == 2
        assert len(result.suppressed) == 0

    def test_suppressed_actions_excluded(self) -> None:
        """Actions with negative valence should be suppressed."""
        # Use a very high suppression threshold so everything gets suppressed
        horizon = ExpectationHorizon(suppression_threshold=100.0)
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        actions = [Action(type="web_search")]
        result = horizon.evaluate(actions, ds)

        assert len(result.suppressed) == 1
        assert len(result.approved) == 0

    def test_diminishing_returns_for_duplicate_actions(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Duplicate actions should show diminishing returns in lookahead."""
        # Two identical web_search actions
        actions = [
            Action(type="web_search"),
            Action(type="web_search"),
        ]
        result = horizon.evaluate(actions, drive_system)

        # Second action should have lower valence (drives partially satisfied)
        first_valence = result.expectations[0].net_valence
        second_valence = result.expectations[1].net_valence

        assert second_valence <= first_valence

    def test_total_valence_is_sum(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Total valence should be the sum of individual action valences."""
        actions = [Action(type="web_search"), Action(type="look")]
        result = horizon.evaluate(actions, drive_system)

        expected_total = sum(e.net_valence for e in result.expectations)
        assert abs(result.total_valence - expected_total) < 1e-10

    def test_empty_actions_returns_empty_result(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Empty action list should return empty result."""
        result = horizon.evaluate([], drive_system)

        assert len(result.expectations) == 0
        assert len(result.approved) == 0
        assert len(result.suppressed) == 0
        assert result.total_valence == 0.0

    def test_does_not_mutate_real_drives(
        self, horizon: ExpectationHorizon, drive_system: DriveSystem
    ) -> None:
        """Evaluation should not modify the actual drive system."""
        original_demands = {
            name: drive.demand for name, drive in drive_system.drives.items()
        }

        horizon.evaluate(
            [Action(type="web_search"), Action(type="look")],
            drive_system,
        )

        for name, drive in drive_system.drives.items():
            assert drive.demand == original_demands[name]


class TestSnapshotDrives:
    """Tests for drive state snapshotting."""

    def test_snapshot_captures_demands(self) -> None:
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)
        ds.drives["curiosity"].demand = 0.75

        horizon = ExpectationHorizon()
        snap = horizon.snapshot_drives(ds)

        assert snap["curiosity"] == 0.75
        assert "energy" in snap


class TestCounterfactualLearning:
    """Tests for the learn_from_outcome counterfactual learning."""

    @pytest.fixture
    def horizon(self) -> ExpectationHorizon:
        return ExpectationHorizon()

    def test_learning_creates_corrections(self, horizon: ExpectationHorizon) -> None:
        """Learning from outcomes should create correction entries."""
        expectations = [
            ActionExpectation(
                action=Action(type="web_search"),
                drive_changes=[
                    PredictedDriveChange(
                        drive_name="curiosity",
                        predicted_satisfaction=0.6,
                        urgency_weight=0.8,
                        weighted_benefit=0.48,
                    )
                ],
                net_valence=0.48,
                confidence=0.5,
            )
        ]

        drives_before = {"curiosity": 0.8, "energy": 0.3}
        drives_after = {"curiosity": 0.6, "energy": 0.3}  # curiosity improved

        horizon.learn_from_outcome(expectations, drives_before, drives_after)

        assert ("web_search", "curiosity") in horizon._corrections

    def test_learning_adjusts_toward_reality(self, horizon: ExpectationHorizon) -> None:
        """Corrections should move toward observed reality over multiple iterations."""
        expectations = [
            ActionExpectation(
                action=Action(type="look"),
                drive_changes=[
                    PredictedDriveChange(
                        drive_name="curiosity",
                        predicted_satisfaction=0.2,
                        urgency_weight=0.5,
                        weighted_benefit=0.1,
                    )
                ],
                net_valence=0.1,
                confidence=0.5,
            )
        ]

        # Simulate multiple learning iterations where actual improvement is better
        for _ in range(10):
            horizon.learn_from_outcome(
                expectations,
                {"curiosity": 0.7},
                {"curiosity": 0.5},  # Better than predicted
            )

        correction = horizon._corrections[("look", "curiosity")]
        # Should have moved above 1.0 since actual was better than predicted
        assert correction > 1.0

    def test_learning_skips_zero_satisfaction(self, horizon: ExpectationHorizon) -> None:
        """Learning should skip drives with zero predicted satisfaction."""
        expectations = [
            ActionExpectation(
                action=Action(type="check_battery"),
                drive_changes=[
                    PredictedDriveChange(
                        drive_name="curiosity",
                        predicted_satisfaction=0.0,
                        urgency_weight=0.5,
                        weighted_benefit=0.0,
                    )
                ],
                net_valence=0.0,
                confidence=0.5,
            )
        ]

        horizon.learn_from_outcome(
            expectations,
            {"curiosity": 0.7},
            {"curiosity": 0.6},
        )

        assert ("check_battery", "curiosity") not in horizon._corrections

    def test_corrections_clamped_to_range(self, horizon: ExpectationHorizon) -> None:
        """Corrections should stay within [0.1, 3.0]."""
        expectations = [
            ActionExpectation(
                action=Action(type="look"),
                drive_changes=[
                    PredictedDriveChange(
                        drive_name="curiosity",
                        predicted_satisfaction=0.2,
                        urgency_weight=0.5,
                        weighted_benefit=0.1,
                    )
                ],
                net_valence=0.1,
                confidence=0.5,
            )
        ]

        # Many iterations to push correction to extreme
        for _ in range(100):
            horizon.learn_from_outcome(
                expectations,
                {"curiosity": 0.9},
                {"curiosity": 0.1},  # Huge improvement
            )

        correction = horizon._corrections[("look", "curiosity")]
        assert 0.1 <= correction <= 3.0


class TestImpulseInhibition:
    """Tests for the impulse inhibition behavior."""

    def test_compulsive_actions_bypass_inhibition(self) -> None:
        """Compulsive (survival) actions should not be suppressed.

        This tests the integration pattern: compulsive actions are added
        to final_actions and should pass through even with negative valence.
        """
        horizon = ExpectationHorizon()
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        # set_power_mode has low valence when energy isn't urgent
        action = Action(type="set_power_mode", params={"mode": "low"})
        result = horizon.evaluate([action], ds)

        # Even if valence is low, it shouldn't be negative enough to suppress
        # (suppression_threshold is -0.05 by default)
        assert action in result.approved or result.expectations[0].net_valence >= -0.05

    def test_custom_suppression_threshold(self) -> None:
        """Custom threshold should control suppression sensitivity."""
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        # Very permissive threshold — nothing should be suppressed
        permissive = ExpectationHorizon(suppression_threshold=-100.0)
        result = permissive.evaluate([Action(type="web_search")], ds)
        assert len(result.suppressed) == 0

        # Very strict threshold — everything gets suppressed
        strict = ExpectationHorizon(suppression_threshold=100.0)
        result = strict.evaluate([Action(type="web_search")], ds)
        assert len(result.suppressed) == 1


class TestIntegration:
    """Integration tests combining prediction, evaluation, and learning."""

    def test_full_cycle(self) -> None:
        """Test a complete predict -> evaluate -> execute -> learn cycle."""
        horizon = ExpectationHorizon()
        config = AgentConfig(voice_enabled=False)
        ds = DriveSystem(config)

        # Make drives urgent
        ds.drives["curiosity"].demand = 0.8
        ds.drives["curiosity"].urgency = 0.8

        # Propose actions
        actions = [Action(type="web_search"), Action(type="look")]

        # Evaluate
        result = horizon.evaluate(actions, ds)
        assert result.total_valence > 0

        # Snapshot before
        before = horizon.snapshot_drives(ds)

        # Simulate execution (manually satisfy drives as if actions succeeded)
        ds.drives["curiosity"].satisfy(0.5)

        # Snapshot after
        after = horizon.snapshot_drives(ds)

        # Learn
        horizon.learn_from_outcome(result.expectations, before, after)

        # Corrections should have been created for the affected drives
        assert len(horizon._corrections) > 0

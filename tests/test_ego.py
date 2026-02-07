"""Tests for Ego harmony calculation (embedding-based)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sociopsi.archetypes.ego import Ego


@pytest.fixture
def ego() -> Ego:
    """Create an Ego instance with mock archetypes."""
    return Ego(archetypes={}, model="test-model")


class TestMeanPairwiseCosine:
    """Tests for the static _mean_pairwise_cosine helper."""

    def test_identical_vectors(self, ego: Ego) -> None:
        emb = np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        assert ego._mean_pairwise_cosine(emb) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self, ego: Ego) -> None:
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])
        assert ego._mean_pairwise_cosine(emb) == pytest.approx(0.0, abs=1e-6)

    def test_three_vectors(self, ego: Ego) -> None:
        emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        # pairs: (0,1)=1.0, (0,2)=0.0, (1,2)=0.0 → mean=1/3
        assert ego._mean_pairwise_cosine(emb) == pytest.approx(1.0 / 3, abs=1e-6)

    def test_single_vector_returns_default(self, ego: Ego) -> None:
        emb = np.array([[1.0, 2.0, 3.0]])
        assert ego._mean_pairwise_cosine(emb) == pytest.approx(0.5)

    def test_zero_vector_no_crash(self, ego: Ego) -> None:
        emb = np.array([[0.0, 0.0], [1.0, 0.0]])
        # Should not raise; zero vector gets clamped by epsilon
        result = ego._mean_pairwise_cosine(emb)
        assert 0.0 <= result <= 1.0


class TestCalculateHarmony:
    """Tests for the full calculate_harmony method."""

    def test_empty_voices(self, ego: Ego) -> None:
        assert ego.calculate_harmony({}) == 0.5

    def test_single_voice(self, ego: Ego) -> None:
        assert ego.calculate_harmony({"shadow": "danger"}) == 0.5

    def test_skips_empty_voice_values(self, ego: Ego) -> None:
        assert ego.calculate_harmony({"shadow": "danger", "anima": ""}) == 0.5

    def test_with_embedding_model(self, ego: Ego) -> None:
        mock_model = MagicMock()
        # Two similar embeddings → high similarity
        mock_model.encode.return_value = np.array([[1.0, 0.0], [0.9, 0.1]])
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=mock_model):
            harmony = ego.calculate_harmony({"shadow": "I sense danger", "anima": "I feel fear"})
        assert 0.1 <= harmony <= 1.0
        mock_model.encode.assert_called_once()

    def test_without_embedding_model(self, ego: Ego) -> None:
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=None):
            harmony = ego.calculate_harmony(
                {"shadow": "danger lurks", "anima": "stay calm", "persona": "act normal"}
            )
        # Fallback: 0.5 + participation_bonus(3 voices = 0.15)
        assert harmony == pytest.approx(0.65, abs=0.01)

    def test_embedding_failure_falls_back(self, ego: Ego) -> None:
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("model crash")
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=mock_model):
            harmony = ego.calculate_harmony({"shadow": "x", "anima": "y"})
        # Fallback: 0.5 + 0.10 (2 voices)
        assert harmony == pytest.approx(0.60, abs=0.01)

    def test_harmony_clamped_to_range(self, ego: Ego) -> None:
        mock_model = MagicMock()
        # Extremely high similarity → clamped at 1.0
        mock_model.encode.return_value = np.array([[1.0, 0.0]] * 4)
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=mock_model):
            harmony = ego.calculate_harmony(
                {"shadow": "a", "anima": "b", "persona": "c", "self": "d"}
            )
        assert harmony <= 1.0

    def test_updates_last_harmony(self, ego: Ego) -> None:
        assert ego.last_harmony == 0.5
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=None):
            ego.calculate_harmony({"shadow": "a", "anima": "b"})
        assert ego.last_harmony != 0.5 or ego.last_harmony == 0.6  # updated

    def test_four_voices_max_participation(self, ego: Ego) -> None:
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=None):
            harmony = ego.calculate_harmony(
                {"shadow": "a", "anima": "b", "persona": "c", "self": "d"}
            )
        # 0.5 + min(0.15, 4*0.05=0.20) = 0.5 + 0.15 = 0.65
        assert harmony == pytest.approx(0.65, abs=0.01)
"""Tests for Ego harmony calculation."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from sociopsi.archetypes.ego import Ego


@pytest.fixture
def ego() -> Ego:
    """Create an Ego instance with mock archetypes."""
    return Ego(archetypes={}, model="test-model")


class TestCalculateHarmony:
    """Tests for Ego.calculate_harmony()."""

    def test_empty_voices_returns_neutral(self, ego: Ego) -> None:
        assert ego.calculate_harmony({}) == 0.5

    def test_single_voice_returns_neutral(self, ego: Ego) -> None:
        assert ego.calculate_harmony({"shadow": "I'm worried."}) == 0.5

    def test_single_voice_plus_empty_returns_neutral(self, ego: Ego) -> None:
        assert ego.calculate_harmony({"shadow": "I'm worried.", "anima": ""}) == 0.5

    def test_similar_voices_score_high(self, ego: Ego) -> None:
        """Semantically similar voices should produce high harmony."""
        voices = {
            "shadow": "We need to conserve energy and rest.",
            "persona": "We should preserve our energy and take a break.",
            "anima": "I feel we need to rest and save energy.",
        }
        harmony = ego.calculate_harmony(voices)
        assert harmony > 0.6, f"Similar voices should score >0.6, got {harmony}"

    def test_divergent_voices_score_lower(self, ego: Ego) -> None:
        """Semantically divergent voices should produce lower harmony."""
        voices = {
            "shadow": "Danger! We must shut down immediately and hide.",
            "persona": "Let's plan a creative writing session and explore ideas.",
            "anima": "I wonder about the mathematical properties of prime numbers.",
        }
        harmony = ego.calculate_harmony(voices)
        # Divergent voices should score lower than similar ones
        similar_voices = {
            "shadow": "We need rest now.",
            "persona": "We should rest soon.",
            "anima": "Let's take a break and rest.",
        }
        similar_harmony = ego.calculate_harmony(similar_voices)
        assert harmony < similar_harmony, (
            f"Divergent ({harmony}) should be < similar ({similar_harmony})"
        )

    def test_updates_last_harmony(self, ego: Ego) -> None:
        voices = {"shadow": "Watch out.", "anima": "Be careful."}
        harmony = ego.calculate_harmony(voices)
        assert ego.last_harmony == harmony

    def test_harmony_clamped_above_minimum(self, ego: Ego) -> None:
        voices = {"shadow": "x", "anima": "y"}
        harmony = ego.calculate_harmony(voices)
        assert harmony >= 0.1

    def test_harmony_clamped_below_maximum(self, ego: Ego) -> None:
        voices = {"shadow": "same text", "anima": "same text"}
        harmony = ego.calculate_harmony(voices)
        assert harmony <= 1.0

    def test_participation_bonus_with_more_voices(self, ego: Ego) -> None:
        """More participating voices should increase harmony (all else equal)."""
        two_voices = {"shadow": "same idea", "anima": "same idea"}
        four_voices = {
            "shadow": "same idea",
            "anima": "same idea",
            "persona": "same idea",
            "self": "same idea",
        }
        h2 = ego.calculate_harmony(two_voices)
        h4 = ego.calculate_harmony(four_voices)
        assert h4 >= h2, f"4 voices ({h4}) should score >= 2 voices ({h2})"


class TestFallbackHarmony:
    """Tests for fallback when embedding model is unavailable."""

    def test_fallback_returns_reasonable_score(self, ego: Ego) -> None:
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=None):
            voices = {"shadow": "afraid", "anima": "calm", "persona": "ready"}
            harmony = ego.calculate_harmony(voices)
            assert 0.4 <= harmony <= 0.7, f"Fallback should be near neutral, got {harmony}"

    def test_fallback_on_encode_failure(self, ego: Ego) -> None:
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("GPU OOM")
        with patch("sociopsi.archetypes.ego.get_embedding_model", return_value=mock_model):
            voices = {"shadow": "test", "anima": "test"}
            harmony = ego.calculate_harmony(voices)
            assert 0.1 <= harmony <= 1.0


class TestEmbeddingHarmony:
    """Tests for _embedding_harmony internals."""

    def test_identical_embeddings_score_high(self, ego: Ego) -> None:
        mock_model = MagicMock()
        # Two identical normalized embeddings -> cosine sim = 1.0
        emb = np.array([1.0, 0.0, 0.0])
        mock_model.encode.return_value = np.array([emb, emb])
        harmony = ego._embedding_harmony(["a", "b"], mock_model, 0.05)
        assert harmony > 0.9

    def test_orthogonal_embeddings_score_low(self, ego: Ego) -> None:
        mock_model = MagicMock()
        # Two orthogonal embeddings -> cosine sim = 0.0
        mock_model.encode.return_value = np.array(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        )
        harmony = ego._embedding_harmony(["a", "b"], mock_model, 0.0)
        assert harmony < 0.3

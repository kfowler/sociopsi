"""Tests for the spreading activation node net."""

import pytest

from sociopsi.nodenet import (
    MAX_ACTIVATION,
    MAX_EDGES_PER_NODE,
    MIN_ACTIVATION,
    Edge,
    Node,
    NodeNet,
)


class TestNode:
    """Tests for the Node dataclass."""

    def test_node_defaults(self) -> None:
        node = Node(concept="test")
        assert node.concept == "test"
        assert node.activation == 0.0
        assert node.emotional_valence == 0.0
        assert node.activation_count == 0

    def test_node_custom_values(self) -> None:
        node = Node(concept="energy", activation=0.8, emotional_valence=-0.5)
        assert node.activation == 0.8
        assert node.emotional_valence == -0.5


class TestEdge:
    """Tests for the Edge dataclass."""

    def test_edge_defaults(self) -> None:
        edge = Edge(source="a", target="b")
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.weight == 0.1


class TestNodeNetAddNode:
    """Tests for node creation and management."""

    def test_add_new_node(self) -> None:
        net = NodeNet()
        node = net.add_node("Energy")
        assert node.concept == "energy"
        assert "energy" in net.nodes

    def test_add_duplicate_returns_existing(self) -> None:
        net = NodeNet()
        n1 = net.add_node("Energy")
        n2 = net.add_node("energy")
        assert n1 is n2

    def test_add_node_normalizes_case(self) -> None:
        net = NodeNet()
        net.add_node("HELLO")
        assert "hello" in net.nodes

    def test_add_node_strips_whitespace(self) -> None:
        net = NodeNet()
        net.add_node("  hello  ")
        assert "hello" in net.nodes

    def test_add_empty_concept_raises(self) -> None:
        net = NodeNet()
        with pytest.raises(ValueError, match="empty"):
            net.add_node("")

    def test_add_whitespace_only_raises(self) -> None:
        net = NodeNet()
        with pytest.raises(ValueError, match="empty"):
            net.add_node("   ")

    def test_add_node_updates_valence(self) -> None:
        net = NodeNet()
        net.add_node("fear", emotional_valence=-0.8)
        net.add_node("fear", emotional_valence=0.5)
        # Blended: -0.8 * 0.7 + 0.5 * 0.3 = -0.41
        assert net.nodes["fear"].emotional_valence == pytest.approx(-0.41, abs=0.01)

    def test_add_node_zero_valence_no_update(self) -> None:
        net = NodeNet()
        net.add_node("calm", emotional_valence=0.5)
        net.add_node("calm", emotional_valence=0.0)
        assert net.nodes["calm"].emotional_valence == 0.5

    def test_capacity_eviction(self) -> None:
        net = NodeNet(max_nodes=3)
        net.add_node("a")
        net.add_node("b")
        net.add_node("c")
        # Activate b and c so they survive eviction
        net.nodes["b"].activation = 0.5
        net.nodes["c"].activation = 0.5
        net.add_node("d")
        assert len(net.nodes) == 3
        assert "d" in net.nodes


class TestNodeNetAddEdge:
    """Tests for edge creation."""

    def test_add_edge_creates_nodes(self) -> None:
        net = NodeNet()
        edge = net.add_edge("fear", "anxiety")
        assert edge is not None
        assert "fear" in net.nodes
        assert "anxiety" in net.nodes

    def test_self_edge_returns_none(self) -> None:
        net = NodeNet()
        assert net.add_edge("fear", "fear") is None

    def test_empty_edge_returns_none(self) -> None:
        net = NodeNet()
        assert net.add_edge("", "fear") is None
        assert net.add_edge("fear", "") is None

    def test_duplicate_edge_strengthens(self) -> None:
        net = NodeNet()
        e1 = net.add_edge("fear", "anxiety", weight=0.2)
        e2 = net.add_edge("fear", "anxiety", weight=0.2)
        assert e1 is e2
        assert e1.weight > 0.2

    def test_edge_weight_capped(self) -> None:
        net = NodeNet()
        for _ in range(50):
            net.add_edge("a", "b", weight=0.5)
        edge = net.edges["a"][0]
        assert edge.weight <= 1.0

    def test_edge_capacity_evicts_weakest(self) -> None:
        net = NodeNet()
        net.add_node("source")
        # Add MAX_EDGES_PER_NODE edges
        for i in range(MAX_EDGES_PER_NODE):
            net.add_edge("source", f"target_{i}", weight=0.5)
        # Weaken one edge
        net.edges["source"][0].weight = 0.01
        # Adding one more should evict the weakest
        net.add_edge("source", "new_target", weight=0.5)
        assert len(net.edges["source"]) == MAX_EDGES_PER_NODE


class TestActivation:
    """Tests for node activation."""

    def test_activate_new_concept(self) -> None:
        net = NodeNet()
        net.activate("music", amount=0.7)
        assert net.nodes["music"].activation == pytest.approx(0.7)
        assert net.nodes["music"].activation_count == 1

    def test_activate_stacks(self) -> None:
        net = NodeNet()
        net.activate("music", amount=0.4)
        net.activate("music", amount=0.4)
        assert net.nodes["music"].activation == pytest.approx(0.8)
        assert net.nodes["music"].activation_count == 2

    def test_activate_capped_at_max(self) -> None:
        net = NodeNet()
        net.activate("music", amount=1.5)
        assert net.nodes["music"].activation == MAX_ACTIVATION

    def test_activate_concepts_creates_edges(self) -> None:
        net = NodeNet()
        net.activate_concepts(["sun", "warmth", "comfort"])
        # Should have bidirectional edges between all pairs
        assert any(e.target == "warmth" for e in net.edges["sun"])
        assert any(e.target == "sun" for e in net.edges["warmth"])
        assert any(e.target == "comfort" for e in net.edges["sun"])

    def test_activate_concepts_activates_all(self) -> None:
        net = NodeNet()
        net.activate_concepts(["a", "b", "c"], amount=0.6)
        for key in ("a", "b", "c"):
            assert net.nodes[key].activation == pytest.approx(0.6)

    def test_activate_concepts_filters_empty(self) -> None:
        net = NodeNet()
        net.activate_concepts(["a", "", "  ", "b"])
        assert len(net.nodes) == 2


class TestSpreading:
    """Tests for spreading activation."""

    def test_spread_propagates(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.5)
        net.nodes["a"].activation = 0.8

        net.spread()

        # b should have received some activation
        assert net.nodes["b"].activation > 0.0

    def test_spread_decays_source(self) -> None:
        net = NodeNet()
        net.add_node("a")
        net.nodes["a"].activation = 1.0

        net.spread()

        assert net.nodes["a"].activation < 1.0

    def test_spread_respects_weight(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.8)
        net.add_edge("a", "c", weight=0.1)
        net.nodes["a"].activation = 1.0

        net.spread()

        # b should have more activation than c
        assert net.nodes["b"].activation > net.nodes["c"].activation

    def test_inactive_nodes_dont_spread(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.5)
        # a has activation below MIN_ACTIVATION
        net.nodes["a"].activation = MIN_ACTIVATION * 0.5

        net.spread()

        # b should not have received activation (only decay applies)
        assert net.nodes["b"].activation == 0.0

    def test_full_decay_to_zero(self) -> None:
        net = NodeNet(decay_rate=0.5)  # High decay rate
        net.add_node("a")
        net.nodes["a"].activation = MIN_ACTIVATION * 1.5  # 0.015

        net.spread()

        # After 50% decay: 0.015 * 0.5 = 0.0075 < MIN_ACTIVATION, zeroed
        assert net.nodes["a"].activation == 0.0

    def test_edge_weight_decays(self) -> None:
        net = NodeNet()
        edge = net.add_edge("a", "b", weight=0.5)

        net.spread()

        assert edge.weight < 0.5

    def test_multiple_spreads_cascade(self) -> None:
        """Activation should cascade through a chain: a -> b -> c."""
        net = NodeNet(decay_rate=0.1)  # Slow decay for chaining
        net.add_edge("a", "b", weight=0.8)
        net.add_edge("b", "c", weight=0.8)
        net.nodes["a"].activation = 1.0

        # First spread: a -> b
        net.spread()
        b_after_1 = net.nodes["b"].activation
        assert b_after_1 > 0.0
        assert net.nodes["c"].activation == 0.0 or net.nodes["c"].activation < b_after_1

        # Second spread: b -> c (and a -> b continues)
        net.spread()
        assert net.nodes["c"].activation > 0.0


class TestHebbianLearning:
    """Tests for Hebbian weight updates."""

    def test_coactive_nodes_strengthen(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.2)
        net.nodes["a"].activation = 0.8
        net.nodes["b"].activation = 0.8

        initial_weight = net.edges["a"][0].weight
        net.hebbian_update()
        assert net.edges["a"][0].weight > initial_weight

    def test_inactive_nodes_dont_strengthen(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.2)
        net.nodes["a"].activation = 0.01  # Below priming threshold
        net.nodes["b"].activation = 0.01

        net.hebbian_update()
        assert net.edges["a"][0].weight == 0.2

    def test_hebbian_weight_capped(self) -> None:
        net = NodeNet(hebbian_rate=10.0)
        net.add_edge("a", "b", weight=0.9)
        net.nodes["a"].activation = 1.0
        net.nodes["b"].activation = 1.0

        net.hebbian_update()
        assert net.edges["a"][0].weight <= 1.0


class TestUpdate:
    """Tests for the combined update cycle."""

    def test_update_spreads_and_learns(self) -> None:
        net = NodeNet()
        net.add_edge("a", "b", weight=0.5)
        net.nodes["a"].activation = 1.0
        net.nodes["b"].activation = 0.5

        initial_weight = net.edges["a"][0].weight
        net.update()

        # Activation should have spread and decayed
        assert net.nodes["a"].activation < 1.0
        # Weight should have changed (hebbian update)
        assert net.edges["a"][0].weight != initial_weight


class TestPriming:
    """Tests for priming context generation."""

    def test_get_primed_returns_active(self) -> None:
        net = NodeNet()
        net.activate("hot", amount=0.8)
        net.activate("cold", amount=0.05)

        primed = net.get_primed()
        concepts = [c for c, _ in primed]
        assert "hot" in concepts
        assert "cold" not in concepts

    def test_get_primed_sorted_by_activation(self) -> None:
        net = NodeNet()
        net.activate("a", amount=0.3)
        net.activate("b", amount=0.9)
        net.activate("c", amount=0.5)

        primed = net.get_primed()
        activations = [a for _, a in primed]
        assert activations == sorted(activations, reverse=True)

    def test_get_primed_respects_count(self) -> None:
        net = NodeNet()
        for i in range(10):
            net.activate(f"concept_{i}", amount=0.5)
        assert len(net.get_primed(3)) == 3

    def test_get_priming_context_empty(self) -> None:
        net = NodeNet()
        assert net.get_priming_context() == ""

    def test_get_priming_context_format(self) -> None:
        net = NodeNet()
        net.activate("music", amount=0.7)
        net.nodes["music"].emotional_valence = 0.5

        ctx = net.get_priming_context()
        assert "[PRIMING]" in ctx
        assert "music" in ctx
        assert "(+)" in ctx

    def test_get_priming_context_negative_valence(self) -> None:
        net = NodeNet()
        net.activate("fear", amount=0.7)
        net.nodes["fear"].emotional_valence = -0.5

        ctx = net.get_priming_context()
        assert "(-)" in ctx

    def test_get_priming_context_neutral_valence(self) -> None:
        net = NodeNet()
        net.activate("data", amount=0.7)
        # Default valence is 0.0 (neutral)

        ctx = net.get_priming_context()
        assert "(+)" not in ctx
        assert "(-)" not in ctx


class TestAssociations:
    """Tests for querying associations."""

    def test_get_associated_empty(self) -> None:
        net = NodeNet()
        assert net.get_associated("unknown") == []

    def test_get_associated_returns_targets(self) -> None:
        net = NodeNet()
        net.add_edge("fear", "anxiety", weight=0.8)
        net.add_edge("fear", "darkness", weight=0.3)

        assocs = net.get_associated("fear")
        assert len(assocs) == 2
        assert assocs[0][0] == "anxiety"  # Strongest first
        assert assocs[1][0] == "darkness"

    def test_get_associated_respects_count(self) -> None:
        net = NodeNet()
        for i in range(10):
            net.add_edge("hub", f"spoke_{i}", weight=0.5)
        assert len(net.get_associated("hub", count=3)) == 3


class TestEviction:
    """Tests for node eviction when at capacity."""

    def test_evict_removes_inactive(self) -> None:
        net = NodeNet(max_nodes=2)
        net.add_node("active")
        net.nodes["active"].activation = 1.0
        net.nodes["active"].activation_count = 10
        net.add_node("inactive")
        # inactive has 0 activation, 0 count

        net.add_node("new")
        assert "new" in net.nodes
        assert "active" in net.nodes
        assert "inactive" not in net.nodes

    def test_evict_cleans_edges(self) -> None:
        net = NodeNet(max_nodes=2)
        net.add_edge("a", "b")
        net.nodes["a"].activation = 1.0
        net.nodes["a"].activation_count = 10

        net.add_node("c")
        # b was evicted, so edges referencing it should be gone
        for edge in net.edges.get("a", []):
            assert edge.target != "b"


class TestGetState:
    """Tests for state reporting."""

    def test_empty_state(self) -> None:
        net = NodeNet()
        state = net.get_state()
        assert state["node_count"] == 0
        assert state["edge_count"] == 0
        assert state["primed"] == []

    def test_populated_state(self) -> None:
        net = NodeNet()
        net.activate("music", amount=0.8)
        net.add_edge("music", "joy", weight=0.5)

        state = net.get_state()
        assert state["node_count"] == 2
        assert state["edge_count"] == 1
        assert "music" in state["primed"]


class TestIntegrationScenario:
    """Integration tests simulating real agent usage."""

    def test_perception_priming_cycle(self) -> None:
        """Simulate: perceive concepts -> spread -> check priming."""
        net = NodeNet()

        # Agent perceives "music" and "relaxation" together
        net.activate_concepts(["music", "relaxation", "evening"])

        # Run a few cycles
        for _ in range(3):
            net.update()

        # Concepts should still be somewhat active
        primed = net.get_primed()
        assert len(primed) > 0

    def test_association_learning(self) -> None:
        """Repeatedly co-activating concepts should strengthen association."""
        net = NodeNet()

        # Repeatedly co-activate "coffee" and "morning"
        for _ in range(10):
            net.activate_concepts(["coffee", "morning"], amount=0.5)
            net.update()
            # Re-inject to keep them active
            net.activate("coffee", amount=0.3)
            net.activate("morning", amount=0.3)

        # Association should be strong
        assocs = net.get_associated("coffee")
        morning_assoc = next((w for c, w in assocs if c == "morning"), 0.0)
        assert morning_assoc > 0.1

    def test_network_remains_bounded(self) -> None:
        """Even with many activations, network stays within bounds."""
        net = NodeNet(max_nodes=50)

        for i in range(100):
            net.activate_concepts([f"concept_{i}", f"concept_{i+1}"], amount=0.5)
            net.update()

        assert len(net.nodes) <= 50

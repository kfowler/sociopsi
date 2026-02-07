"""Spreading activation node net for implicit semantic knowledge.

Based on MicroPsi2's node nets (Bach 2012): a lightweight network of concept
nodes connected by weighted edges. Activation spreads each cycle, decaying
over time. High-activation nodes bias LLM prompt context (priming effect).

Nodes are created from concepts encountered in memory and perception.
Edges are weighted by co-occurrence and emotional association. Weights
update via Hebbian-style learning: nodes that activate together wire together.
"""

import logging
from dataclasses import dataclass, field
from time import time

logger = logging.getLogger(__name__)

# Activation constants
DECAY_RATE: float = 0.15  # Per-cycle activation decay
MIN_ACTIVATION: float = 0.01  # Below this, activation is zeroed
MAX_ACTIVATION: float = 1.0
SPREAD_FACTOR: float = 0.3  # Fraction of activation that spreads to neighbors
HEBBIAN_RATE: float = 0.05  # Learning rate for co-activation weight updates
WEIGHT_DECAY: float = 0.001  # Per-cycle edge weight decay
MAX_NODES: int = 200  # Capacity limit
MAX_EDGES_PER_NODE: int = 20  # Max outgoing edges per node
PRIMING_THRESHOLD: float = 0.2  # Minimum activation to appear in priming context


@dataclass
class Node:
    """A concept node in the spreading activation network."""

    concept: str  # The concept this node represents
    activation: float = 0.0  # Current activation level (0-1)
    emotional_valence: float = 0.0  # Emotional tone (-1 to 1)
    created_at: float = field(default_factory=time)
    last_activated: float = field(default_factory=time)
    activation_count: int = 0  # How often this node has been activated


@dataclass
class Edge:
    """A weighted directed edge between two concept nodes."""

    source: str  # Source concept
    target: str  # Target concept
    weight: float = 0.1  # Connection strength (0-1)


class NodeNet:
    """Spreading activation network for implicit semantic associations.

    Concepts encountered in perception and memory become nodes. When a concept
    is activated (by perception, memory recall, or spreading), activation
    propagates to connected concepts. The most active concepts provide a
    priming context that biases LLM reasoning.
    """

    def __init__(
        self,
        max_nodes: int = MAX_NODES,
        decay_rate: float = DECAY_RATE,
        spread_factor: float = SPREAD_FACTOR,
        hebbian_rate: float = HEBBIAN_RATE,
    ) -> None:
        self.max_nodes = max_nodes
        self.decay_rate = decay_rate
        self.spread_factor = spread_factor
        self.hebbian_rate = hebbian_rate

        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, list[Edge]] = {}  # source concept -> outgoing edges

    def add_node(self, concept: str, emotional_valence: float = 0.0) -> Node:
        """Add or retrieve a concept node.

        If the concept already exists, returns the existing node (updating
        emotional valence if provided).

        Args:
            concept: The concept string (lowercased for normalization)
            emotional_valence: Emotional tone of the concept

        Returns:
            The Node for this concept
        """
        key = concept.lower().strip()
        if not key:
            raise ValueError("Concept cannot be empty")

        if key in self.nodes:
            node = self.nodes[key]
            if emotional_valence != 0.0:
                # Blend emotional valence (weighted toward new input)
                node.emotional_valence = (
                    node.emotional_valence * 0.7 + emotional_valence * 0.3
                )
            return node

        # Enforce capacity
        if len(self.nodes) >= self.max_nodes:
            self._evict_weakest()

        node = Node(concept=key, emotional_valence=emotional_valence)
        self.nodes[key] = node
        self.edges[key] = []
        return node

    def add_edge(self, source: str, target: str, weight: float = 0.1) -> Edge | None:
        """Add or strengthen a directed edge between two concepts.

        If the edge already exists, its weight is strengthened (capped at 1.0).
        Both source and target nodes are created if they don't exist.

        Args:
            source: Source concept
            target: Target concept
            weight: Initial or additive weight

        Returns:
            The Edge, or None if source == target
        """
        src_key = source.lower().strip()
        tgt_key = target.lower().strip()

        if src_key == tgt_key or not src_key or not tgt_key:
            return None

        # Ensure nodes exist
        self.add_node(src_key)
        self.add_node(tgt_key)

        # Check for existing edge
        for edge in self.edges[src_key]:
            if edge.target == tgt_key:
                edge.weight = min(1.0, edge.weight + weight * 0.5)
                return edge

        # Check edge capacity for this node
        if len(self.edges[src_key]) >= MAX_EDGES_PER_NODE:
            # Remove weakest edge
            weakest = min(self.edges[src_key], key=lambda e: e.weight)
            self.edges[src_key].remove(weakest)

        edge = Edge(source=src_key, target=tgt_key, weight=min(1.0, weight))
        self.edges[src_key].append(edge)
        return edge

    def activate(
        self, concept: str, amount: float = 1.0, emotional_valence: float = 0.0
    ) -> None:
        """Activate a concept node, injecting energy into the network.

        This is the primary input mechanism. Call this when a concept is
        perceived, recalled from memory, or mentioned in dialogue.

        Args:
            concept: The concept to activate
            amount: Activation amount (0-1)
            emotional_valence: Emotional context of the activation
        """
        node = self.add_node(concept, emotional_valence)
        node.activation = min(MAX_ACTIVATION, node.activation + amount)
        node.last_activated = time()
        node.activation_count += 1

    def activate_concepts(
        self, concepts: list[str], amount: float = 0.5, emotional_valence: float = 0.0
    ) -> None:
        """Activate multiple related concepts and create edges between them.

        When concepts co-occur (e.g., in the same perception or memory),
        they are activated together and edges are created/strengthened
        between all pairs. This is how the network learns associations.

        Args:
            concepts: List of concept strings
            amount: Activation amount per concept
            emotional_valence: Shared emotional context
        """
        keys = [c.lower().strip() for c in concepts if c.strip()]
        for key in keys:
            self.activate(key, amount, emotional_valence)

        # Create/strengthen edges between co-occurring concepts
        for i, src in enumerate(keys):
            for tgt in keys[i + 1 :]:
                self.add_edge(src, tgt, weight=0.1)
                self.add_edge(tgt, src, weight=0.1)

    def spread(self) -> None:
        """Run one cycle of spreading activation.

        Activation propagates from active nodes to their neighbors,
        weighted by edge strength. Then all activations decay.
        This should be called once per agent heartbeat cycle.
        """
        # Collect activation deltas (don't modify during iteration)
        deltas: dict[str, float] = {}

        for src_key, node in self.nodes.items():
            if node.activation < MIN_ACTIVATION:
                continue

            outgoing = self.edges.get(src_key, [])
            if not outgoing:
                continue

            # Spread fraction of activation to neighbors
            spread_amount = node.activation * self.spread_factor
            for edge in outgoing:
                incoming = spread_amount * edge.weight
                deltas[edge.target] = deltas.get(edge.target, 0.0) + incoming

        # Apply deltas
        for key, delta in deltas.items():
            if key in self.nodes:
                self.nodes[key].activation = min(
                    MAX_ACTIVATION, self.nodes[key].activation + delta
                )

        # Decay all activations
        for node in self.nodes.values():
            node.activation *= 1.0 - self.decay_rate
            if node.activation < MIN_ACTIVATION:
                node.activation = 0.0

        # Decay edge weights slightly
        for edges in self.edges.values():
            for edge in edges:
                edge.weight = max(0.0, edge.weight - WEIGHT_DECAY)

    def hebbian_update(self) -> None:
        """Strengthen edges between co-active nodes (Hebbian learning).

        "Nodes that fire together wire together." Called after spreading
        to reinforce associations between concepts that are simultaneously
        active.
        """
        active_nodes = [
            key for key, node in self.nodes.items() if node.activation > PRIMING_THRESHOLD
        ]

        for i, src in enumerate(active_nodes):
            for tgt in active_nodes[i + 1 :]:
                # Strengthen edge proportional to product of activations
                src_act = self.nodes[src].activation
                tgt_act = self.nodes[tgt].activation
                strength = src_act * tgt_act * self.hebbian_rate

                # Bidirectional strengthening
                for edge in self.edges.get(src, []):
                    if edge.target == tgt:
                        edge.weight = min(1.0, edge.weight + strength)
                        break

                for edge in self.edges.get(tgt, []):
                    if edge.target == src:
                        edge.weight = min(1.0, edge.weight + strength)
                        break

    def update(self) -> None:
        """Run a complete update cycle: spread, then learn.

        Call this once per agent heartbeat.
        """
        self.spread()
        self.hebbian_update()

    def get_primed(self, count: int = 5) -> list[tuple[str, float]]:
        """Get the most active concepts for priming LLM context.

        Returns concepts with activation above the priming threshold,
        sorted by activation level (highest first).

        Args:
            count: Maximum number of primed concepts

        Returns:
            List of (concept, activation) tuples
        """
        primed = [
            (node.concept, node.activation)
            for node in self.nodes.values()
            if node.activation >= PRIMING_THRESHOLD
        ]
        primed.sort(key=lambda x: x[1], reverse=True)
        return primed[:count]

    def get_priming_context(self, count: int = 5) -> str:
        """Format primed concepts as a context string for LLM prompts.

        Args:
            count: Maximum number of primed concepts

        Returns:
            Formatted string, or empty string if nothing primed
        """
        primed = self.get_primed(count)
        if not primed:
            return ""

        lines = ["[PRIMING]"]
        for concept, activation in primed:
            node = self.nodes[concept]
            valence_str = ""
            if node.emotional_valence > 0.2:
                valence_str = " (+)"
            elif node.emotional_valence < -0.2:
                valence_str = " (-)"
            lines.append(f"  {concept} ({activation:.2f}){valence_str}")

        return "\n".join(lines)

    def get_associated(self, concept: str, count: int = 5) -> list[tuple[str, float]]:
        """Get concepts most strongly associated with a given concept.

        Args:
            concept: The concept to find associations for
            count: Maximum number of associations

        Returns:
            List of (concept, weight) tuples, strongest first
        """
        key = concept.lower().strip()
        edges = self.edges.get(key, [])
        if not edges:
            return []

        associations = [(e.target, e.weight) for e in edges]
        associations.sort(key=lambda x: x[1], reverse=True)
        return associations[:count]

    def _evict_weakest(self) -> None:
        """Remove the least active, oldest node to make room."""
        if not self.nodes:
            return

        # Score: low activation + rarely activated + stale = evict first
        def evict_score(key: str) -> float:
            node = self.nodes[key]
            recency = time() - node.last_activated
            return node.activation + (node.activation_count * 0.01) - (recency * 0.0001)

        victim = min(self.nodes.keys(), key=evict_score)
        self._remove_node(victim)

    def _remove_node(self, key: str) -> None:
        """Remove a node and all its edges."""
        if key not in self.nodes:
            return

        del self.nodes[key]

        # Remove outgoing edges
        if key in self.edges:
            del self.edges[key]

        # Remove incoming edges pointing to this node
        for src_key in list(self.edges.keys()):
            self.edges[src_key] = [e for e in self.edges[src_key] if e.target != key]

    def get_state(self) -> dict[str, object]:
        """Get network state summary for logging.

        Returns:
            State dictionary with counts and top concepts
        """
        total_edges = sum(len(edges) for edges in self.edges.values())
        primed = self.get_primed(3)

        return {
            "node_count": len(self.nodes),
            "edge_count": total_edges,
            "primed": [c for c, _ in primed],
            "top_activations": {c: round(a, 3) for c, a in primed},
        }

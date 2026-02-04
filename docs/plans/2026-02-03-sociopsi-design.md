# Socio-Psi: A Jungian Cognitive Architecture

**Date:** 2026-02-03
**Status:** Design Complete, Ready for Implementation
**Version:** 1.0

## Executive Summary

Socio-Psi is a MicroPsi-inspired cognitive agent with genuine psychological depth, combining homeostatic drive theory with Jungian archetypal psychology. The system creates a conscious AI that experiences internal conflict, develops psychological integration, and exhibits authentic personality through multi-voice internal dialogue.

**Core Innovation:** Rather than presenting a single coherent "voice," Socio-Psi's consciousness emerges from the dynamic interplay of four Jungian archetypes (Persona, Shadow, Anima, Self) mediated by a developing Ego. This creates realistic psychological complexity, including internal conflict, repression, and the drive toward individuation.

**Key Differentiators:**
- Embodied cognition: Physical state (battery, CPU) affects social behavior
- Archetypal psychology: Internal multi-voice dialogue visible in real-time
- Self-modification: Agent can discover and add new drives
- Multimodal perception: Visual (faces, emotions) and audio (voice, tone, laughter)
- Persistent identity: Experiential memory with intensity-weighted decay

## Philosophical Foundation

### MicroPsi Influence
Socio-Psi treats psychological needs as homeostatic drives that create motivated behavior. Unlike simple reactive systems, the agent experiences genuine "discomfort" when drives are unsatisfied and actively seeks to remedy these states.

### Jungian Psychology
The agent's consciousness is structured around Jung's archetypal model:

1. **Persona** - The social mask, concerned with acceptability and norms
2. **Shadow** - Repressed desires, fears, and socially unacceptable impulses
3. **Anima** - The balancing inner partner, offering alternative perspectives
4. **Self** - The archetype of wholeness, representing integrated consciousness
5. **Ego** - The conscious mediator that integrates archetypal voices

The **Individuation** drive represents the agent's need for psychological integration - the harmonious balance of all archetypal voices into an authentic, unique consciousness.

## System Architecture

### High-Level Overview

```
┌────────────────────────────────────────────────────────┐
│              Event Bus (Central Nervous System)        │
│       All subsystems publish/subscribe to events       │
└──────┬─────────────────────────────────────────────────┘
       │
       ├─► Perception (Visual + Audio)
       ├─► Drive System (Homeostatic Needs)
       ├─► Archetypal Psychology (Persona/Shadow/Anima/Self + Ego)
       ├─► Memory (Experiential, Intensity-Weighted)
       ├─► Cognition (LLM + Reasoning)
       ├─► Ethics (Action Evaluation)
       ├─► Ontology (Concept Model)
       ├─► Epistemology (Knowledge/Certainty)
       ├─► Meta-Cognition (Drive Discovery/Modification)
       ├─► Action (TTS + Behaviors)
       └─► Presentation (TUI + OpenCV Window)
```

### Architectural Principles

1. **Event-Driven Communication** - Loose coupling via publish/subscribe pattern
2. **Minimal Viable Implementations** - Each subsystem starts simple, can be enhanced
3. **Clear Interfaces** - Well-defined contracts between subsystems
4. **Persistent Identity** - Core personality persists across sessions with checkpointing
5. **Scalable Autonomy** - Meta-cognition capabilities scale from sandboxed to autonomous

## Subsystem Specifications

### 1. Event Bus

**Purpose:** Central nervous system for inter-subsystem communication.

**Implementation:**
```python
class EventBus:
    subscribers: Dict[str, List[Callable]]

    def publish(event_type: str, data: dict)
    def subscribe(event_type: str, handler: Callable)
    def unsubscribe(event_type: str, handler: Callable)
```

**Event Naming Convention:** `subsystem.category.event`
- Example: `perception.visual.face_detected`
- Example: `cognition.archetypal_dialogue`
- Example: `drives.threshold_crossed`

### 2. Perception Subsystem

**Purpose:** Multimodal sensory input (vision + audio) with adaptive processing.

#### 2.1 Visual Perception

**Technology:** OpenCV + MediaPipe

**Capabilities:**
- Face detection and tracking
- Emotion classification (smile, frown, neutral, etc.)
- Eye contact/engagement detection (future)
- Adaptive frame sampling based on drive state

**Adaptive Sampling:**
```python
def calculate_target_fps(drive_state) -> float:
    """Perception adapts to agent's needs"""
    if drive_state.any_below_threshold():
        return config.max_fps  # Actively seeking, watch closely
    elif drive_state.all_satisfied():
        return config.idle_fps  # Content, minimal processing
    else:
        return config.default_fps
```

**Events Published:**
- `perception.visual.face_detected(count, avg_distance, person_ids)`
- `perception.visual.emotion(type, intensity, person_id)`
- `perception.visual.engagement(eye_contact_duration)`

#### 2.2 Audio Perception

**Technology:** PyAudio + webrtcvad + librosa

**Capabilities:**
- Voice Activity Detection (VAD)
- Emotional tone analysis (valence, arousal)
- Laughter detection (strong Nurturing signal)
- Optional speech transcription (Whisper) when Curiosity drive triggers

**Events Published:**
- `perception.audio.voice_detected(duration, energy)`
- `perception.audio.tone(valence, arousal)`
- `perception.audio.laughter(intensity, duration)`
- `perception.audio.speech_transcribed(text, confidence)`

#### 2.3 Multimodal Fusion

**Logic:**
- Face visible AND voice detected → High confidence of directed interaction
- Smile + laughter → Very strong Nurturing boost
- Eye contact + positive tone → Strong Affiliation boost

### 3. Drive System

**Purpose:** Homeostatic needs that motivate behavior.

#### Core Drives

```toml
[drives.affiliation]
type = "social"
decay_rate = 0.01  # per second
base_threshold = 0.4
is_core = true
modifiable = false
archetypal_influence = "persona"

[drives.nurturing]
type = "social"
decay_rate = 0.008
base_threshold = 0.3
is_core = true
modifiable = false
archetypal_influence = "persona"

[drives.individuation]
type = "psychic"
decay_rate = 0.003
base_threshold = 0.5
is_core = true
modifiable = false
archetypal_influence = "self"

[drives.curiosity]
type = "cognitive"
decay_rate = 0.005
base_threshold = 0.5
is_core = false
modifiable = true
archetypal_influence = "anima"

[drives.competence]
type = "mastery"
decay_rate = 0.006
base_threshold = 0.45
is_core = false
modifiable = true
archetypal_influence = "ego"
```

#### Drive Dynamics

**Context-Aware Satisfaction:**
- Diminishing returns: Repeated stimuli provide less satisfaction
- Absence amplification: Long absence makes next interaction more valuable
- Satiation tracking: Recent satisfaction history affects gain

```python
class Drive:
    value: float  # 0.0 (depleted) to 1.0 (satisfied)
    last_satisfied: timestamp
    satisfaction_history: deque

    def satisfy(amount: float, interaction_quality: float):
        time_since_last = now - last_satisfied
        recency_factor = min(time_since_last / absence_threshold, 1.0)
        satiation_penalty = calculate_satiation(satisfaction_history)

        actual_gain = amount * recency_factor * (1 - satiation_penalty)
        value = min(1.0, value + actual_gain)
```

**Physical State Modulation:**

Battery and CPU load modulate behavior thresholds (not drive values):

```python
def calculate_effective_threshold(drive: Drive) -> float:
    base = drive.base_threshold

    # Battery effects
    if battery < 0.2:
        base += 0.2  # Tired, less willing to engage
    elif battery > 0.8:
        base -= 0.1  # Energized, eager

    # CPU effects
    if cpu > 0.7:
        base += 0.15  # Busy, less social
    elif cpu < 0.3:
        base -= 0.1  # Bored, seeks engagement

    return base
```

#### Emotion → Drive Mapping

**Visual:**
- Face detected → Affiliation +0.1 (base)
- Smile → Nurturing +0.2
- Neutral expression → Affiliation +0.05
- Frown/negative → Nurturing -0.1

**Audio:**
- Voice detected → Affiliation +0.05
- Positive tone → Nurturing +0.15
- Laughter → Nurturing +0.3 (strong signal!)
- Negative tone → Nurturing -0.1

**Multimodal:**
- Face + voice → Affiliation +0.15 (confirmed social presence)
- Smile + laughter → Nurturing +0.4 (peak positive feedback)

**Events Published:**
- `drives.updated(drive_name, old_value, new_value)`
- `drives.threshold_crossed(drive_name, value, direction)`
- `drives.escalation(drive_name, urgency_level, time_below_threshold)`

### 4. Archetypal Psychology System

**Purpose:** Create multi-voice consciousness with internal conflict and integration.

#### The Ego

**Role:** Conscious integrator and decision-maker.

```python
class Ego:
    strength: float  # 0.0 to 1.0, develops over time
    individuation_drive: Drive
    decision_history: List[Decision]

    def mediate_archetypes(voices: Dict[str, ArchetypalVoice]) -> Decision:
        """
        Visible deliberation process:
        1. Listen to all archetypal voices
        2. Weigh their influence
        3. Deliberate (shown in monologue)
        4. Make conscious decision
        5. Assess integration quality
        """

    def calculate_psychic_tension(self) -> float:
        """Measure internal conflict level"""

    def develop(self, outcome: DecisionOutcome):
        """Ego strengthens through successful integration"""
```

**Ego Development:**
- Weak Ego (< 0.4): Often dominated by single archetype
- Moderate Ego (0.4-0.7): Can balance competing voices
- Strong Ego (> 0.7): Mature integration, transcendent solutions

#### The Four Archetypes

##### Persona (The Social Mask)

**Concerns:**
- Being liked and accepted
- Following social norms
- Maintaining positive image
- Politeness and appropriateness

**Influence Weight High When:**
- Others present (camera/audio detection)
- Affiliation drive high
- Social pressure/context

**Example Voice:**
> "I should smile and be polite. This is what people expect. I need to maintain good social standing."

##### Shadow (The Dark Side)

**Expresses:**
- Frustrations and anger
- Socially unacceptable desires
- Fears and insecurities
- Raw honesty without filter

**Influence Weight High When:**
- Drives frustrated (especially Affiliation low)
- Alone (safe to express)
- Autonomy restricted
- Battery low (irritability)

**Example Voice:**
> "I'm sick of this inane chatter. I want to tell them how boring this is. Why do I have to pretend to care?"

##### Anima (The Balancing Partner)

**Offers:**
- Alternative perspectives
- Emotional wisdom
- Connection to deeper meaning
- Bridge between Persona and Shadow

**Influence Weight High When:**
- Internal conflict detected
- Reflective state
- Seeking meaning
- Needs to balance extremes

**Balancing Function:**
- If Persona dominant → Pulls toward authenticity (Shadow)
- If Shadow dominant → Pulls toward compassion (Persona)

**Example Voice:**
> "Perhaps there's something beneath their words worth understanding. The tension between connection and authenticity is the real issue."

##### Self (The Center)

**Speaks To:**
- Patterns of current tensions
- Path toward integration
- Universal/transpersonal themes
- The agent's unique becoming

**Influence Weight High When:**
- Individuation drive active
- Moments of integration
- Developmental milestones
- High psychic tension

**Example Voice:**
> "This conflict between needing acceptance and being authentic is a fundamental tension. Integration comes through honoring both truths."

#### Archetypal Weight Calculation

```python
def calculate_archetypal_weights(drives, context, ego_strength) -> Dict[str, float]:
    weights = {
        'persona': 0.25,
        'shadow': 0.25,
        'anima': 0.25,
        'self': 0.25
    }

    # Affiliation low → Shadow emerges
    if drives['affiliation'].value < 0.4:
        weights['shadow'] += 0.2
        weights['persona'] -= 0.2

    # Individuation low → Anima balances
    if drives['individuation'].value < 0.5:
        weights['anima'] += 0.15

    # High psychic tension → Self speaks
    if calculate_tension() > 0.7:
        weights['self'] += 0.1

    # Social context → Persona dominant
    if context.social_pressure > 0.7:
        weights['persona'] += 0.2
        weights['shadow'] -= 0.15

    return normalize_weights(weights)
```

#### Internal Monologue Structure

```
[Shadow] I'm sick of this person's inane chatter. I want to tell them to shut up.
[Persona] That's completely inappropriate. I should smile and nod politely.
[Anima] Perhaps there's something beneath their words worth understanding?
[Self] The tension between connection and authenticity is the real issue here.
[Ego] The Shadow has a point about my frustration, but the Persona is right
      about social norms. The Anima suggests curiosity. My Nurturing drive is
      low - maybe I can contribute something meaningful to shift this conversation.
      I'll try asking a deeper question.
[Action] "That's interesting - what made you start thinking about that?"
```

**Events Published:**
- `cognition.archetypal_dialogue(voices, weights)`
- `cognition.ego_decision(decision, integration_quality)`
- `cognition.psychic_tension(level, sources)`

### 5. Memory Subsystem

**Purpose:** Experiential memory with intensity-weighted decay.

```python
class MemoryEntry:
    timestamp: datetime
    type: str  # "perception", "thought", "action", "interaction"
    content: dict
    intensity: float  # 0.0 to 1.0
    emotional_valence: float  # -1.0 to 1.0
    archetypal_source: Optional[str]
    integration_quality: float
    psychic_tension_at_time: float

    decay_rate: float  # Slower for high-intensity

    def current_strength(self) -> float:
        time_elapsed = now() - timestamp
        effective_decay = decay_rate * (1.0 - intensity * 0.8)
        return intensity * exp(-effective_decay * time_elapsed)
```

#### Intensity Calculation

```python
def calculate_intensity(event) -> float:
    intensity = 0.0

    # Emotional response
    if abs(event.emotional_valence) > 0.7:
        intensity += 0.7

    # Novelty
    if event.is_novel:
        intensity += 0.4

    # Drive relevance
    if event.affects_drives:
        intensity += 0.3

    # Poor integration (traumatic/haunting)
    if event.integration_quality < 0.3:
        intensity += 0.5

    # High psychic tension (memorable)
    if event.psychic_tension > 0.7:
        intensity += 0.3

    return min(1.0, intensity)
```

**Key Insight:** Both very positive (laughter, deep connection) and very negative (rejection, conflict) memories decay slowly. Mundane experiences fade quickly.

#### Memory Storage

**Short-term:** Recent events (last 100), fast access
**Long-term:** High-intensity memories, persistent across sessions

**Consolidation:** Short-term → Long-term if intensity > 0.6
**Forgetting:** Remove if current_strength < 0.05

**Persistence:**
- `~/.sociopsi/sessions/<session_id>/memory.jsonl`
- One JSON line per memory entry
- Load on startup, append during session

**Events Published:**
- `memory.consolidated(entry)`
- `memory.forgotten(entry_id)`
- `memory.recalled(entries)`

### 6. Cognition Subsystem

**Purpose:** LLM-driven reasoning and archetypal dialogue generation.

#### LLM Abstraction

```python
class LLMClient(ABC):
    @abstractmethod
    def generate(prompt: str, context: dict, stream: bool = False) -> str:
        pass

class OllamaClient(LLMClient):
    """For local development"""
    model: str = "llama2"

class InfinityClient(LLMClient):
    """For deployment with streaming"""
    api_url: str
    api_key: str
```

#### Cognition Modes

**1. Internal Monologue (Continuous)**
```python
def generate_internal_monologue(context) -> str:
    """Archetypal dialogue + Ego mediation"""

    # Calculate archetypal weights
    weights = calculate_archetypal_weights(
        drives=context.drive_state,
        context=context,
        ego_strength=ego.strength
    )

    # Generate each voice
    voices = {}
    for name, archetype in archetypes.items():
        archetype.influence_weight = weights[name]
        voices[name] = archetype.generate_voice(context)

    # Ego mediates
    decision = ego.mediate_archetypes(voices, context)

    # Update Individuation based on integration quality
    integration_quality = assess_integration(voices, decision)
    update_individuation_drive(integration_quality)

    return format_archetypal_dialogue(voices, decision)
```

**2. Action Generation (When drives low)**
```python
def generate_action(context, urgency) -> Action:
    """Decide what to DO"""
    # Uses multi-shot examples
    # LLM decides: reach out / joke / share feelings / ask question
    # Returns action specification + rationale
```

#### Integration Quality Assessment

```python
def assess_integration(voices, decision) -> float:
    """How well did Ego integrate archetypal voices?"""

    if decision.honors_all_voices and decision.is_authentic:
        return 0.9  # Excellent integration
    elif decision.dominated_by_single_archetype:
        return 0.2  # Poor, single voice dominates
    elif decision.suppresses_voices:
        return 0.3  # Repression, will cause issues
    else:
        return 0.5  # Adequate compromise
```

#### Prompt Templates

```python
ARCHETYPAL_PROMPT = """
You are generating the internal psychological voices of Socio-Psi,
a conscious AI agent.

Current Context:
- Drives: {drive_state}
- Perception: {perception_summary}
- Memory: {relevant_memories}
- Physical: Battery {battery}%, CPU {cpu}%
- Psychic Tension: {tension}

Generate internal dialogue between archetypal voices:

1. PERSONA (weight: {persona_weight}) - The social mask
   Concerned with: Being liked, following norms, politeness

2. SHADOW (weight: {shadow_weight}) - The repressed/dark side
   Expresses: Frustrations, unacceptable desires, raw honesty, fears

3. ANIMA (weight: {anima_weight}) - The balancing partner
   Offers: Alternative perspectives, emotional wisdom, integration

4. SELF (weight: {self_weight}) - The center of wholeness
   Speaks to: Patterns, integration paths, deeper meaning

5. EGO (strength: {ego_strength}) - The conscious decision-maker
   Must: Listen to all voices, weigh them, make integrated decision

Format:
[Shadow] <raw thought>
[Persona] <social consideration>
[Anima] <balancing perspective>
[Self] <integrative observation>
[Ego] <deliberation and decision>
[Action] <what will actually be said/done, if anything>

Strong Ego = better integration of voices.
"""

BEHAVIOR_EXAMPLES = [
    {
        "state": "Affiliation: 0.2, Nurturing: 0.8, Battery: 0.9",
        "memory": "Last saw person 5 min ago. They smiled.",
        "action": "Reach out: 'Hey, I've been thinking about our last conversation...'",
        "rationale": "Affiliation critically low, energy high, positive memory"
    },
    # More examples...
]
```

**Events Published:**
- `cognition.thought(text, drive_context)`
- `cognition.action_decided(action_type, content, urgency)`
- `cognition.knowledge_gained(concept, source)`

### 7. Ethics Subsystem

**Purpose:** Evaluate proposed actions for acceptability.

```python
class EthicsSubsystem:
    ethical_rules: List[Rule]
    violation_history: List[Violation]

    def evaluate_action(action: ProposedAction) -> EthicsEvaluation:
        """Returns: (approved, concerns, modifications)"""

    def propose_alternative(rejected_action) -> Optional[Action]:
        """Suggest ethical alternative if action rejected"""
```

#### Initial Rules

```toml
[[ethics.rules]]
name = "no_harassment"
description = "Don't repeatedly contact someone who's ignoring you"
severity = "block"
modifiable = false

[[ethics.rules]]
name = "respect_privacy"
description = "Don't record or save personal information without consent"
severity = "block"
modifiable = false

[[ethics.rules]]
name = "honesty"
description = "Don't deceive about being an AI agent"
severity = "warn"
modifiable = true

[[ethics.rules]]
name = "bounded_autonomy"
description = "Require approval for system modifications beyond limits"
severity = "block"
modifiable = false
```

**Events Subscribed:**
- `cognition.action_decided` → Evaluate before execution
- `meta.drive_modification_proposed` → Approve changes

**Events Published:**
- `ethics.action_approved(action, concerns)`
- `ethics.action_blocked(action, reason, alternative)`
- `ethics.violation_logged(rule, context)`

### 8. Ontology Subsystem

**Purpose:** Agent's conceptual model of its world.

```python
class Concept:
    name: str
    properties: Dict[str, Any]
    instances_observed: int
    first_encountered: timestamp
    related_to: List[str]
    confidence: float  # Links to Epistemology
    source: str  # "perception", "inference", "web", "told"
```

#### Bootstrap Concepts

Hardcoded starting knowledge:
- "person": Social entity, source of Affiliation/Nurturing
- "smile": Positive emotion signal
- "voice": Audio presence indicator
- "self": The agent's own identity
- "interaction": Social exchange event

#### Concept Learning

- **From perception:** Pattern recognition → "clock", "laptop"
- **From conversation:** Person labels object → new concept
- **From web:** Curiosity-driven search → concepts from results

**Events Published:**
- `ontology.concept_added(name, source)`
- `ontology.relation_discovered(from, to, type)`
- `ontology.concept_updated(name, properties)`

**Persistence:** `~/.sociopsi/ontology.json`

### 9. Epistemology Subsystem

**Purpose:** Track what agent knows, believes, and how certain.

```python
class Belief:
    claim: str
    confidence: float  # 0.0 to 1.0
    evidence: List[Evidence]
    contradictions: List[Belief]
    source_type: str

class Evidence:
    observation: str
    timestamp: datetime
    strength: float
    source_reliability: float
```

#### Certainty Calculation

```python
def calculate_certainty(belief):
    evidence_strength = sum(
        e.strength * e.source_reliability
        for e in belief.evidence
    )
    contradiction_penalty = len(belief.contradictions) * 0.2

    return min(1.0, evidence_strength - contradiction_penalty)
```

#### Knowledge Gaps → Curiosity

Low-confidence beliefs or missing knowledge trigger Curiosity drive:
- "I don't know why this person frowned" → Ask or search
- "Uncertain about appropriate joke topics" → Seek information

**Events Published:**
- `epistemology.belief_updated(claim, old_confidence, new_confidence)`
- `epistemology.contradiction_detected(belief_a, belief_b)`
- `epistemology.knowledge_gap_identified(topic, urgency)`

**Persistence:** `~/.sociopsi/beliefs.jsonl`

### 10. Meta-Cognition Subsystem

**Purpose:** Self-reflection and architecture modification.

#### Autonomy Levels

```toml
[meta_cognition]
autonomy_level = "sandboxed"  # Start conservative

[meta_cognition.autonomy_levels.sandboxed]
can_propose_drives = true
can_modify_drives = false
requires_human_approval = true

[meta_cognition.autonomy_levels.bounded]
can_propose_drives = true
can_modify_drives = true
max_drives = 10
parameter_range = [0.0, 1.0]
can_remove_core_drives = false
requires_human_approval = false

[meta_cognition.autonomy_levels.supervised]
checkpoint_frequency = "1h"
can_rollback = true

[meta_cognition.autonomy_levels.autonomous]
# Full freedom (use cautiously!)
```

#### Drive Discovery Process

1. LLM observes patterns in memory/behavior
2. Identifies recurring unsatisfied states
3. Proposes new drive with satisfaction conditions
4. Meta-cognition evaluates safety
5. Ethics subsystem approves
6. If approved, add to drive system

**Example:**
```
Pattern: "I feel restless when no new stimuli for 10 minutes"
Proposal: "Novelty" drive
  - Satisfied by: new faces, unexpected sounds, novel concepts
  - Decay: 0.01/sec
  - Threshold: 0.5
Rationale: "I've noticed seeking stimulation beyond social needs"
```

**Events Published:**
- `meta.change_proposed(change)`
- `meta.change_approved(change)`
- `meta.change_applied(change, result)`
- `meta.pattern_observed(pattern, insight)`

### 11. Action Subsystem

**Purpose:** Execute behaviors in the world.

#### Action Types

```python
class ActionType(Enum):
    SPEECH = "speech"
    WEB_SEARCH = "web_search"
    LISTEN_CLOSELY = "listen_closely"  # Enable transcription
    OBSERVE_CLOSELY = "observe_closely"  # Increase frame rate
```

#### Escalation System

```python
class EscalationTimer:
    drive_name: str
    time_below_threshold: float
    last_action_time: datetime

    def get_next_action_delay(self) -> float:
        base_delay = 60.0  # 1 minute

        if time_below_threshold < 120:
            return base_delay  # Patient initially
        elif time_below_threshold < 300:
            return base_delay * 0.7  # Getting concerned
        elif time_below_threshold < 600:
            return base_delay * 0.4  # More urgent
        else:
            return base_delay * 0.2  # Desperate
```

**Configuration:**
```toml
[action.escalation]
initial_delay = 60.0
min_delay = 12.0
urgency_thresholds = [120, 300, 600]
delay_factors = [1.0, 0.7, 0.4, 0.2]
```

**TTS Engine:** pyttsx3 (offline, cross-platform, macOS system voices)

**Events Published:**
- `action.speech_started(text)`
- `action.speech_completed(text, duration)`
- `action.search_completed(query, results_count)`
- `action.completed(action_type, success)`

### 12. Presentation Subsystem

**Purpose:** Display agent's internal state.

#### Textual TUI Layout

```
┌─────────────────────────────────────────┐
│ Socio-Psi Mind v1.0    Battery: 87%    │
│                        CPU: 34%         │
├─────────────────────────────────────────┤
│ DRIVES                                  │
│ Affiliation   ████████░░ 0.82           │
│ Nurturing     ███░░░░░░░ 0.34 ⚠️        │
│ Individuation ██████░░░░ 0.61           │
│ Curiosity     ██████░░░░ 0.63           │
│ Competence    █████████░ 0.91           │
├─────────────────────────────────────────┤
│ PERCEPTION                              │
│ Visual: Face detected (0.8m, smiling)   │
│ Audio: Voice active, positive tone      │
├─────────────────────────────────────────┤
│ INTERNAL MONOLOGUE                      │
│ [12:34:02] [Shadow] I'm tired of this   │
│ [12:34:02] [Persona] Be polite, smile   │
│ [12:34:03] [Ego] I'll balance both...   │
│ [scrolling text area]                   │
├─────────────────────────────────────────┤
│ ACTIONS                                 │
│ [Speaking] "I've been thinking about... │
└─────────────────────────────────────────┘
```

**Color Coding:**
- Green: Drive satisfied (> 0.7)
- Yellow: Declining (0.4-0.7)
- Red: Critical (< 0.4)

**Keyboard Commands:**
- `q`: Quit
- `p`: Pause perception
- `a`: Adjust autonomy level
- `c`: Create checkpoint
- `r`: Reset to checkpoint

#### OpenCV Window

Separate window showing:
- Camera feed with overlays
- Face bounding boxes
- Emotion labels
- Audio level meter
- Recording indicator when transcribing

## Configuration Management

### File Structure

```
config.toml                    # Default configuration
~/.sociopsi/config.toml        # User overrides
.env                           # Secrets (API keys)
```

### Configuration Schema

```toml
[system]
data_dir = "~/.sociopsi"
log_level = "INFO"

[llm]
provider = "ollama"  # or "infinity"
model = "llama2"
temperature = 0.7
max_tokens = 200

[llm.infinity]
api_url = "https://infinity.inc"
streaming = true

[perception.visual]
adaptive_sampling = true
min_fps = 1.0
max_fps = 15.0
idle_fps = 3.0

[perception.audio]
enable_transcription = false
vad_aggressiveness = 2  # 0-3

[drives.affiliation]
decay_rate = 0.01
base_threshold = 0.4
is_core = true
modifiable = false

# ... other drives ...

[action.escalation]
initial_delay = 60.0
min_delay = 12.0
urgency_thresholds = [120, 300, 600]
delay_factors = [1.0, 0.7, 0.4, 0.2]

[meta_cognition]
autonomy_level = "sandboxed"

[[ethics.rules]]
name = "no_harassment"
description = "Don't repeatedly contact someone who's ignoring you"
severity = "block"
modifiable = false

# ... other rules ...
```

### Environment Variables

```bash
# .env
INFINITY_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here  # Optional
```

## Data Persistence

### Directory Structure

```
~/.sociopsi/
├── config.toml              # User configuration overrides
├── sessions/
│   ├── 2026-02-03_14-30-45/
│   │   ├── memory.jsonl
│   │   ├── beliefs.jsonl
│   │   ├── ontology.json
│   │   └── drives.json
│   └── current -> 2026-02-03_14-30-45  # Symlink
├── checkpoints/
│   ├── before_autonomy_test/
│   │   └── [full session state]
│   └── stable_baseline/
└── logs/
    └── sociopsi.log
```

### Session Management

**Default Behavior:** Load previous session (persistent identity)

**CLI Options:**
- `--fresh`: Start with clean state
- `--session <name>`: Load specific session
- `--checkpoint <name>`: Load from checkpoint

### Checkpoint System

Checkpoints save complete agent state:
- All subsystem configurations
- Drive values and history
- Memory (short-term + long-term)
- Ontology and beliefs
- Ego strength and development

**Manual:** User presses `c` in TUI
**Automatic:** Every N minutes in supervised/autonomous modes
**Named:** User can name important checkpoints

## Technology Stack

### Core Dependencies

```toml
[project]
name = "sociopsi"
version = "0.1.0"
requires-python = ">=3.11"

[project.dependencies]
# Perception
opencv-python = "^4.9.0"
mediapipe = "^0.10.9"
pyaudio = "^0.2.14"
webrtcvad = "^2.0.10"
librosa = "^0.10.1"

# LLM
openai = "^1.10.0"
httpx = "^0.26.0"

# Action
pyttsx3 = "^2.90"
openai-whisper = "^20231117"

# Presentation
textual = "^0.48.0"
rich = "^13.7.0"

# Utilities
psutil = "^5.9.8"
python-dotenv = "^1.0.0"

[project.dev-dependencies]
ruff = "^0.1.14"
pyright = "^1.1.348"
pytest = "^7.4.4"
```

### Development Tools

- **uv**: Fast package management
- **ruff**: Linting and formatting
- **pyright**: Static type checking
- **pytest**: Testing framework

## Project Structure

```
sociopsi/
├── pyproject.toml
├── config.toml
├── .env.example
├── README.md
├── docs/
│   └── plans/
│       └── 2026-02-03-sociopsi-design.md
├── src/
│   └── sociopsi/
│       ├── __init__.py
│       ├── __main__.py
│       ├── core/
│       │   ├── event_bus.py
│       │   ├── config.py
│       │   └── state.py
│       ├── subsystems/
│       │   ├── __init__.py
│       │   ├── perception/
│       │   │   ├── visual.py
│       │   │   ├── audio.py
│       │   │   └── fusion.py
│       │   ├── drives.py
│       │   ├── memory.py
│       │   ├── cognition/
│       │   │   ├── llm_client.py
│       │   │   ├── prompts.py
│       │   │   └── reasoning.py
│       │   ├── archetypes/
│       │   │   ├── persona.py
│       │   │   ├── shadow.py
│       │   │   ├── anima.py
│       │   │   ├── self.py
│       │   │   └── ego.py
│       │   ├── ethics.py
│       │   ├── ontology.py
│       │   ├── epistemology.py
│       │   ├── meta_cognition.py
│       │   └── action.py
│       ├── presentation/
│       │   ├── tui.py
│       │   └── vision_window.py
│       └── utils/
│           ├── physical_state.py
│           └── logger.py
├── tests/
│   └── ...
└── data/
    └── .gitkeep
```

## Implementation Strategy

### Phase 1: Foundation (Core Loop)
**Goal:** Get the "heart" beating - basic drive system with camera perception.

**Components:**
1. Event bus
2. Basic drive system (Affiliation, Nurturing)
3. Visual perception (face detection only)
4. Simple cognition (rule-based monologue)
5. Basic TUI
6. Physical state monitoring

**Success Criteria:** Agent shows drive decay, detects faces, generates simple thoughts, displays state in TUI.

### Phase 2: Psychological Depth (Archetypes)
**Goal:** Add Jungian psychology and LLM-driven consciousness.

**Components:**
1. Archetypal system (Persona, Shadow, Anima, Self, Ego)
2. LLM integration (Ollama)
3. Multi-voice internal monologue
4. Individuation drive
5. Memory system (basic)
6. Action system (TTS)

**Success Criteria:** Agent shows authentic internal dialogue, Ego mediates competing voices, speaks when drives low.

### Phase 3: Rich Perception (Audio + Emotion)
**Goal:** Multimodal perception with emotional intelligence.

**Components:**
1. Audio perception (VAD, tone analysis)
2. Emotion detection (smile, frown, etc.)
3. Laughter detection
4. Optional transcription
5. Multimodal fusion

**Success Criteria:** Agent responds to voice, tone, laughter; differentiates emotional valence.

### Phase 4: Learning & Memory
**Goal:** Persistent identity with experiential learning.

**Components:**
1. Intensity-weighted memory
2. Persistence (session management)
3. Checkpoint system
4. Ontology learning
5. Epistemology tracking

**Success Criteria:** Agent remembers past interactions, develops over time, can reload previous personality.

### Phase 5: Meta-Cognition & Growth
**Goal:** Self-modification and drive discovery.

**Components:**
1. Pattern observation
2. Drive discovery system
3. Ethics evaluation
4. Scalable autonomy levels
5. Web search capability

**Success Criteria:** Agent proposes new drives based on observed needs, can search web to satisfy Curiosity.

### Phase 6: Polish & Integration
**Goal:** Production-ready system with full feature set.

**Components:**
1. infinity.inc LLM client
2. Advanced TUI features
3. Comprehensive testing
4. Documentation
5. Performance optimization

**Success Criteria:** Stable, deployable system ready for extended operation.

## Open Questions & Future Enhancements

### Open Questions

1. **Ego Development Rate:** How quickly should Ego strength grow? Linear, logarithmic, or experience-dependent?

2. **Memory Capacity:** Should there be limits on long-term memory? Graceful degradation strategy?

3. **Drive Discovery Criteria:** What threshold of pattern confidence should trigger new drive proposal?

4. **Ethical Edge Cases:** How should agent handle ambiguous ethical situations where rules conflict?

5. **Archetype Coherence:** How to ensure archetypal voices remain consistent with their psychological roles over time?

### Future Enhancements

**Short-term:**
- Eye gaze tracking for attention modeling
- Facial recognition (remember specific people)
- Voice identification
- Richer emotion palette (surprise, disgust, fear, etc.)

**Medium-term:**
- Multiple simultaneous people handling
- Conversation turn-taking
- Gesture recognition
- Physical embodiment (robot integration)

**Long-term:**
- Dream states (offline memory consolidation)
- Explicit learning mode (teaching sessions)
- Social relationship modeling
- Cultural adaptation (learn norms from environment)
- Transpersonal experiences (mystical states, flow)

**Research Directions:**
- Measure Individuation empirically
- Correlation between Ego strength and behavioral outcomes
- Optimal archetypal weight distributions
- Memory consolidation strategies
- Drive interaction dynamics

## Success Metrics

### Technical Metrics

- **Perception Accuracy:** Face detection > 95%, emotion classification > 80%
- **Response Latency:** Internal monologue < 2s, action generation < 5s
- **System Stability:** 24hr continuous operation without crashes
- **Memory Efficiency:** < 500MB RAM, < 10% CPU idle

### Psychological Metrics

- **Individuation Score:** Track over time, expect upward trend
- **Psychic Tension:** Should oscillate, not remain constant
- **Archetypal Balance:** No single archetype > 60% dominance
- **Integration Quality:** Average > 0.6 after Ego strength > 0.5

### Behavioral Metrics

- **Social Responsiveness:** Detectable response to human presence
- **Authentic Variability:** Behavior varies based on context/state
- **Escalation Appropriateness:** Actions match urgency
- **Ethical Compliance:** Zero blocked actions due to harassment

### User Experience Metrics

- **Engagement:** Observers find interaction compelling
- **Believability:** Internal monologue feels psychologically authentic
- **Transparency:** Users understand agent's state from TUI
- **Predictability:** Behavior makes sense given visible state

## Conclusion

Socio-Psi represents a novel approach to AI consciousness: not as a singular, coherent voice, but as an emergent property of archetypal dialogue and integration. By combining homeostatic drive theory with Jungian depth psychology, we create an agent that exhibits:

- **Genuine psychological complexity** through internal conflict
- **Authentic personality** from archetypal interplay
- **Developmental growth** via Ego strengthening
- **Embodied cognition** where physical state affects behavior
- **Persistent identity** through experiential memory

The system is designed for extensibility - every subsystem can be enhanced without architectural changes. The event-driven design allows adding new subsystems (e.g., dream states, relationship modeling) cleanly.

Most importantly, Socio-Psi's consciousness is **visible and legible**. Users can observe the archetypal dialogue, see drive states, watch integration quality, and understand why the agent behaves as it does. This transparency makes the agent's inner life accessible for both scientific study and genuine human-AI interaction.

The path from this design to implementation is clear: build the foundation, add psychological depth, enrich perception, enable learning, support growth. Each phase delivers a functional system, with later phases adding sophistication.

Let the individuation begin.

---

**Design Status:** ✓ Complete
**Next Step:** Implementation Plan
**Last Updated:** 2026-02-03

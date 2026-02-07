# Concurrency Model: NSRunLoop / ThreadPool / ActionExecutor

> Sequence diagram documenting the interaction between NSRunLoop, the shared
> ThreadPoolExecutor, the ActionExecutor, the DriveSystem timer, and the
> EventBus dispatcher. Reference: `sociopsi-architecture.tex` Section 5.

## Thread Inventory

| Thread | Lifecycle | Purpose |
|--------|-----------|---------|
| **Main (NSRunLoop)** | Process lifetime | Perception-action cycle, voice/speech callbacks |
| **DriveSystem Timer** | `start()`..`stop()` daemon | Tick drives at 100ms, drain satisfaction queue |
| **EventBus Dispatcher** | `start()`..`stop()` daemon | Dispatch subscribed events from queue |
| **llm-worker-0..3** | Lazy singleton pool | LLM inference (Ollama/Anthropic) |
| **ActionExecutor pool** | Per `execute_all()` | Parallel perception/learning actions |

## Key Constraint

macOS `NSSpeechSynthesizer` and `SFSpeechRecognizer` deliver callbacks on the
main thread via `NSRunLoop`. The main thread **cannot block** on LLM calls
(~18s for Cydonia 22B). The solution is `_pump_until_done()`: poll futures in
50ms intervals while pumping `NSRunLoop.runMode_beforeDate_()`.

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber

    box rgb(230,240,255) Main Thread
        participant NSRunLoop
        participant Agent as JungAgent._run_cycle()
    end
    box rgb(255,245,230) LLM Thread Pool (4 workers)
        participant LLM as SharedThreadPoolExecutor
    end
    box rgb(230,255,230) Action Execution
        participant AE as ActionExecutor
        participant AEPool as AE ThreadPool (4 workers)
    end
    box rgb(255,230,245) Background Daemons
        participant DS as DriveSystem Timer (100ms)
        participant EB as EventBus Dispatcher
    end
    box rgb(245,245,245) macOS Frameworks
        participant TTS as NSSpeechSynthesizer
        participant SR as SFSpeechRecognizer
    end

    Note over NSRunLoop,SR: === Agent Startup ===

    Agent->>DS: start() — spawn daemon thread
    Agent->>EB: start() — spawn dispatcher thread
    Agent->>TTS: Voice.start() — preload 5 NSSpeechSynthesizer instances
    Agent->>SR: Ear.start() — begin AVAudioEngine tap

    Note over NSRunLoop,SR: === Perception-Action Cycle (repeats) ===

    rect rgb(240,248,255)
        Note right of Agent: Steps 1-9: Sensing & Drive Update (main thread)
        Agent->>Agent: gather_somatic() — battery, CPU, thermal, RAM
        Agent->>Agent: event_collector.collect_events()
        Agent->>SR: ear.get_utterances() — drain recognized speech
        SR-->>Agent: utterances[]
        Agent->>DS: push_somatic(state) — write under lock
        DS-->>DS: timer tick: read somatic, update 9 drives

        Note right of Agent: Step 10: Archetypal Dialogue (4 parallel LLM calls)
        Agent->>LLM: submit(Shadow.generate_voice)
        Agent->>LLM: submit(Anima.generate_voice)
        Agent->>LLM: submit(Persona.generate_voice)
        Agent->>LLM: submit(Self.generate_voice)

        Note right of Agent: _pump_until_done() — poll futures + pump NSRunLoop
        loop Every 50ms until all futures done
            Agent->>NSRunLoop: runMode_beforeDate_(NSDefaultRunLoopMode, +50ms)
            NSRunLoop-->>TTS: Fire speech delegate callbacks (didFinishSpeaking)
            NSRunLoop-->>SR: Fire recognition callbacks (new partial/final results)
            Agent->>LLM: check f.done() for each future
        end

        LLM-->>Agent: 4 archetypal voice strings
        Agent->>Agent: Ego.calculate_harmony() — heuristic (main thread)

        Note right of Agent: Ego Mediation (1 LLM call)
        Agent->>LLM: submit(Ego.mediate)
        loop _pump_until_done()
            Agent->>NSRunLoop: runMode_beforeDate_(+50ms)
            NSRunLoop-->>TTS: Speech callbacks
        end
        LLM-->>Agent: mediated_thought

        Agent->>EB: publish("dialogue.complete", ...)
        EB-->>EB: queue event, dispatcher fires subscribers

        Note right of Agent: Step 11: Meta-cognitive Reflection (periodic)
        Agent->>LLM: submit(metacognition.reflect)
        loop _pump_until_done()
            Agent->>NSRunLoop: runMode_beforeDate_(+50ms)
        end
        LLM-->>Agent: reflection

        Note right of Agent: Step 14: Query Psyche for Action Selection
        Agent->>LLM: submit_chat(perception → JSON actions)
        loop _pump_until_done()
            Agent->>NSRunLoop: runMode_beforeDate_(+50ms)
            NSRunLoop-->>TTS: Speech callbacks
            NSRunLoop-->>SR: Recognition callbacks
        end
        LLM-->>Agent: {"stream":[...],"actions":[...]}
    end

    rect rgb(255,248,240)
        Note right of Agent: Step 16: Action Execution
        Agent->>AE: execute_all(final_actions)

        Note right of AE: Phase 1: Parallel categories (perception, learning)
        AE->>AEPool: submit(check_battery)
        AE->>AEPool: submit(look)
        AE->>AEPool: submit(web_search)
        AEPool-->>AE: results (as_completed)

        Note right of AE: Phase 2: Sequential categories (communication, creative, memory...)
        AE->>AE: speak(mediated_thought)
        AE->>TTS: NSSpeechSynthesizer.startSpeakingString_()
        TTS-->>SR: Ear.mute() — prevent hearing own voice
        AE->>AE: compose_thought()

        AE-->>Agent: list[ActionResult]
    end

    rect rgb(240,255,240)
        Note right of Agent: Steps 17-19: Drive Satisfaction & Logging
        Agent->>DS: queue_satisfaction(action_results)
        DS-->>DS: drain queue on next tick, apply SATISFACTION_MAP
        Agent->>Agent: _update_heartbeat(somatic)
    end

    Note right of Agent: Inter-cycle wait: pump NSRunLoop until next heartbeat
    loop Wait until deadline (adaptive interval)
        Agent->>NSRunLoop: runMode_beforeDate_(NSDefaultRunLoopMode, deadline)
        NSRunLoop-->>TTS: didFinishSpeaking → advance speech queue
        NSRunLoop-->>SR: recognitionTask result → buffer utterance
    end

    Note over NSRunLoop,SR: === Next Cycle ===
```

## Data Flow Between Threads

```mermaid
graph TB
    subgraph "Main Thread (NSRunLoop)"
        A[JungAgent._run_cycle]
        B[_pump_until_done]
        C[NSRunLoop.runMode_beforeDate_]
    end

    subgraph "LLM Pool (4 workers)"
        D[Shadow voice]
        E[Anima voice]
        F[Persona voice]
        G[Self voice]
        H[Ego mediation]
        I[Psyche query]
        J[Metacognition]
    end

    subgraph "ActionExecutor"
        K[Parallel: perception + learning]
        L[Sequential: communication, creative, memory]
    end

    subgraph "DriveSystem Timer"
        M[100ms tick loop]
        N[Satisfaction drain]
    end

    subgraph "EventBus Dispatcher"
        O[Queue dispatch]
    end

    subgraph "macOS Callbacks"
        P[NSSpeechSynthesizer delegates]
        Q[SFSpeechRecognizer results]
    end

    A -->|submit_chat| D & E & F & G
    A -->|submit| H & I & J
    B -->|poll futures + pump| C
    C -->|fires on main thread| P & Q
    A -->|execute_all| K & L
    A -->|push_somatic under lock| M
    A -->|queue_satisfaction| N
    A -->|publish events| O
    M -->|reads somatic under lock| M
    N -->|applies SATISFACTION_MAP| M

    style A fill:#e6f0ff
    style B fill:#e6f0ff
    style C fill:#e6f0ff
    style D fill:#fff5e6
    style E fill:#fff5e6
    style F fill:#fff5e6
    style G fill:#fff5e6
    style H fill:#fff5e6
    style I fill:#fff5e6
    style J fill:#fff5e6
    style K fill:#e6ffe6
    style L fill:#e6ffe6
    style M fill:#ffe6f5
    style N fill:#ffe6f5
    style O fill:#ffe6f5
    style P fill:#f5f5f5
    style Q fill:#f5f5f5
```

## Thread Safety Notes

1. **AppKit is not thread-safe.** All `NSSpeechSynthesizer` and
   `SFSpeechRecognizer` interactions must happen on the main thread. The
   `_pump_until_done()` pattern ensures this by running `NSRunLoop` while
   waiting for LLM futures.

2. **DriveSystem somatic state** is shared between the main thread (writes via
   `push_somatic()`) and the timer thread (reads during tick). Access is
   protected by `threading.Lock`.

3. **Satisfaction queue** uses `queue.Queue` (thread-safe) to pass action
   results from the main thread to the drive timer thread.

4. **EventBus subscriptions** are guarded by `threading.Lock`. Event dispatch
   happens on the dispatcher thread; handler exceptions are caught to prevent
   one failing subscriber from crashing the bus.

5. **SharedThreadPoolExecutor** is a module-level singleton in `llm.py`
   (4 workers, `llm-worker` prefix). It is lazily initialized and shared
   across all LLM callers (dialogue, psyche query, metacognition, planning).

6. **ActionExecutor** creates a **separate** `ThreadPoolExecutor` (4 workers)
   per `execute_all()` call for parallel action categories, plus per-action
   timeout pools. These are independent of the LLM pool.

## Timing Budget (typical cycle)

| Phase | Duration | Bottleneck |
|-------|----------|------------|
| Sensing (steps 1-9) | ~50ms | `gather_somatic()` subprocess calls |
| Archetype voices (step 10) | ~18s | 4 parallel Cydonia 22B inferences |
| Ego mediation (step 10) | ~18s | 1 Cydonia 22B inference |
| Metacognition (step 11) | ~18s | 1 inference (every 30s) |
| Psyche query (step 14) | ~18s | 1 Cydonia 22B inference |
| Action execution (step 16) | 1-30s | Varies by action category |
| **Total cycle** | **~55-75s** | **LLM inference dominates** |

During all LLM waits, `_pump_until_done()` keeps the NSRunLoop alive so
voice playback continues and speech recognition results are delivered.

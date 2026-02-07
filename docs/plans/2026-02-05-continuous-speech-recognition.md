# Continuous Speech Recognition via SFSpeechRecognizer

## Overview

Add continuous speech recognition to Socio-Psi using Apple's
SFSpeechRecognizer via PyObjC. The agent listens for human speech at all
times and injects recognized utterances into its perception loop.

## Architecture

New module `src/sociopsi/ear.py` provides the `Ear` class - a singleton
that opens an AVAudioEngine tap on the microphone and feeds audio into
SFSpeechAudioBufferRecognitionRequest. Delegate callbacks deliver partial
and final transcriptions. Final utterances are buffered and drained by
the agent each cycle.

## Flow

```
Microphone -> AVAudioEngine input tap
           -> SFSpeechAudioBufferRecognitionRequest.append()
           -> SFSpeechRecognizer on-device recognition
           -> Delegate callbacks (partial / final)
           -> Final utterances -> deque buffer
           -> Agent drains via get_utterances() each cycle
           -> Injected into perception as [SPEECH] tag
           -> LLM responds naturally to what was said
```

## Timeout Restart

SFSpeechRecognizer tasks time out after ~60 seconds. The Ear detects
task completion and seamlessly restarts: the audio engine tap runs
continuously, only the recognition request/task pair is cycled. Zero
audio gap during restart.

## Perception Integration

Speech appears in the perception string as:

```
[SPEECH]
- "what are you thinking about?"
```

Omitted entirely when no speech was heard. Utterances are also stored
in SemanticMemory with type "interaction" and intensity 0.7.

## Configuration

- `ear_enabled: bool = True`
- `ear_locale: str = "en-US"`
- `ear_on_device: bool = True`

## Permissions

- Microphone access (macOS prompt)
- Speech Recognition (SFSpeechRecognizer.requestAuthorization)

Both degrade gracefully if denied.

## Deliverables

1. `src/sociopsi/ear.py` - Ear class
2. `src/sociopsi/agent.py` - Integration
3. `src/sociopsi/config.py` - Config fields
4. `tests/test_ear.py` - Unit tests

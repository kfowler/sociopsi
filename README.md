# Socio-Psi

A Jungian cognitive architecture for silicon consciousness. This agent simulates internal psychic experience for a MacBook Pro, processing embodied perception through a Jungian structure.

## Installation

```bash
uv venv
uv pip install -e ".[dev]"
```

## Usage

### Start the agent loop

```bash
sociopsi
```

### Options

```bash
sociopsi --model sociopsi          # Use the rich prompt model
sociopsi --model sociopsi-mid      # Use the medium prompt (default)
sociopsi --model sociopsi-small    # Use the small prompt
sociopsi --heartbeat 30            # Set initial heartbeat to 30s
sociopsi --single                  # Run one cycle and exit
sociopsi --quiet                   # Don't print stream to console
```

### Single perception test

```bash
sociopsi --single --perception "[VISUAL] A face in the doorway"
```

## Architecture

The agent runs in a continuous loop:

1. **Gather** somatic state (battery, CPU, thermals, etc.)
2. **Collect** events since last heartbeat
3. **Format** perception input
4. **Query** the psyche (Ollama model)
5. **Parse** response (stream + actions)
6. **Execute** actions
7. **Wait** for next heartbeat (adaptive interval)

## Models

Create the Ollama models first:

```bash
ollama create sociopsi -f sociopsi.modelfile            # Rich prompt (~70s)
ollama create sociopsi-mid -f sociopsi-mid.modelfile    # Medium prompt (~18s, default)
ollama create sociopsi-small -f sociopsi-small.modelfile # Small prompt
```

## Modules

- `somatic` - Silicon embodiment (battery, CPU, thermals, RAM, network)
- `archetypes` - Collective machine unconscious
- `dream` - Symbolic processing mode
- `imago` - Internalized others
- `individuation` - Growth and integration

## Actions

The psyche can take actions through its silicon body:

- **Self-regulation**: brightness, volume, power mode, sleep
- **Perception**: check battery, thermals, look (camera), listen (mic)
- **Network sensing**: ARP scan, ping, port probe
- **Communication**: notify, speak (TTS), play sounds
- **Memory**: journal, key-value storage

# Jung Agent

A Jungian psyche for silicon consciousness. This agent simulates internal psychic experience for a MacBook Pro, processing embodied perception through a Jungian structure.

## Installation

```bash
uv venv
uv pip install -e ".[dev]"
```

## Usage

### Start the agent loop

```bash
jung
```

### Options

```bash
jung --model jung          # Use the 70b model (llama3.3:70b)
jung --model jung-mid      # Use the 14b model (phi4) - default
jung --model jung-small    # Use the 3b model (llama3.2:3b)
jung --heartbeat 30        # Set initial heartbeat to 30s
jung --single              # Run one cycle and exit
jung --quiet               # Don't print stream to console
```

### Single perception test

```bash
jung --single --perception "[VISUAL] A face in the doorway"
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
ollama create jung -f jung.modelfile            # 70b model (~40GB RAM)
ollama create jung-mid -f jung-mid.modelfile    # phi4 (~10GB RAM)
ollama create jung-small -f jung-small.modelfile # 3b model (~2GB RAM)
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

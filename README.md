# Socio-Psi

A Jungian cognitive architecture with homeostatic drives.

## Requirements

- Python 3.11+
- macOS (tested) or Linux
- Webcam

## Installation

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone git@github.com:kfowler/consciousness.git
cd consciousness

# Install dependencies
uv sync --dev
```

## macOS Camera Permissions

On first run, macOS will prompt for camera permissions. If you miss the prompt:

1. Open System Settings → Privacy & Security → Camera
2. Find Terminal (or your terminal app)
3. Enable camera access
4. Restart the application

## Running Socio-Psi

```bash
uv run python -m sociopsi
```

## Controls

- `q`: Quit
- `p`: Pause (not yet implemented)

## Phase 1 Features

- ✅ Drive system (Affiliation, Nurturing)
- ✅ Visual perception (face detection)
- ✅ Simple rule-based cognition
- ✅ Terminal UI with Textual
- ✅ Physical state monitoring (battery, CPU)

## Next Phases

- Phase 2: Archetypal psychology (Persona, Shadow, Anima, Self, Ego)
- Phase 3: Audio perception and emotion detection
- Phase 4: Memory system and persistence
- Phase 5: Meta-cognition and drive discovery
- Phase 6: Production polish

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright
```

## Architecture

See `docs/plans/2026-02-03-sociopsi-design.md` for full design specification.

## License

TBD

"""Entry point for the Jung agent."""

import argparse
import sys

from jung_agent.agent import JungAgent, run_single
from jung_agent.config import AgentConfig


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Jung Agent - A Jungian psyche for silicon consciousness"
    )

    parser.add_argument(
        "--model",
        default="jung-small",
        help="Ollama model to use (default: jung-small)",
    )

    parser.add_argument(
        "--modules",
        nargs="+",
        default=["somatic", "archetypes", "imago", "individuation"],
        help="Modules to enable",
    )

    parser.add_argument(
        "--heartbeat",
        type=int,
        default=None,
        help="Override initial heartbeat interval (seconds)",
    )

    parser.add_argument(
        "--single",
        action="store_true",
        help="Run a single perception-response cycle and exit",
    )

    parser.add_argument(
        "--perception",
        type=str,
        default=None,
        help="Custom perception input (for --single mode)",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't log stream to console",
    )

    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable voice output",
    )

    parser.add_argument(
        "--voice",
        type=str,
        default="Daniel",
        help="Voice name for TTS (default: Daniel)",
    )

    parser.add_argument(
        "--voice-rate",
        type=int,
        default=180,
        help="Voice speed in words per minute (default: 180)",
    )

    args = parser.parse_args()

    # Build config
    config = AgentConfig(
        model=args.model,
        modules=args.modules,
        log_stream=not args.quiet,
        voice_enabled=not args.no_voice,
        voice_name=args.voice,
        voice_rate=args.voice_rate,
    )

    if args.heartbeat:
        config.heartbeat_idle = args.heartbeat

    # Run
    if args.single:
        response = run_single(config, args.perception)
        print(response)
        return 0
    else:
        agent = JungAgent(config)
        agent.start()
        return 0


if __name__ == "__main__":
    sys.exit(main())

"""Entry point for the Jung agent."""

import argparse
import sys

from jung_agent.agent import JungAgent, run_single
from jung_agent.config import AgentConfig, setup_logging


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Jung Agent - A Jungian psyche for silicon consciousness"
    )

    parser.add_argument(
        "--model",
        default="jung-mid",
        help="Ollama model to use (default: jung-mid)",
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
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (enables file logging)",
    )

    args = parser.parse_args()

    # Build config
    config = AgentConfig(
        model=args.model,
        modules=args.modules,
        log_stream=not args.quiet,
        voice_enabled=not args.no_voice,
    )

    if args.heartbeat:
        config.heartbeat_idle = args.heartbeat

    if args.verbose:
        config.log_level = "DEBUG"

    if args.log_file:
        from pathlib import Path
        config.log_file = Path(args.log_file)

    # Set up logging
    setup_logging(config)

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

"""Convenience wrapper to run sociopsi module.

This allows running with 'python main.py' for convenience,
but the canonical way is: uv run python -m sociopsi
"""

if __name__ == "__main__":
    from sociopsi.__main__ import main
    main()

"""Entry point for Socio-Psi."""

import asyncio
from typing import Any

from sociopsi.core.agent import SocioPsiAgent
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiApp(SocioPsiTUI):
    """Socio-Psi application with agent integration."""

    agent: SocioPsiAgent  # Override parent type

    def __init__(self, **kwargs: Any) -> None:
        """Initialize application."""
        super().__init__(**kwargs)
        self.agent = SocioPsiAgent()
        self.agent.tui = self

    async def on_mount(self) -> None:
        """Start agent when app mounts."""
        await super().on_mount()

        # Start agent with error handling
        async def start_agent_with_logging():
            try:
                await self.agent.start()
            except Exception as e:
                import traceback

                print(f"AGENT CRASH: {e}")
                traceback.print_exc()

        asyncio.create_task(start_agent_with_logging())

    def action_quit(self) -> None:
        """Stop agent before quitting."""
        self.agent.running = False  # Stop the agent loop
        self.exit()


def main() -> None:
    """Run Socio-Psi."""
    app = SocioPsiApp()
    app.run()


if __name__ == "__main__":
    main()

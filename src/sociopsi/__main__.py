"""Entry point for Socio-Psi."""

import asyncio
from sociopsi.core.agent import SocioPsiAgent
from sociopsi.presentation.tui import SocioPsiTUI


class SocioPsiApp(SocioPsiTUI):
    """Socio-Psi application with agent integration."""

    def __init__(self, **kwargs) -> None:
        """Initialize application."""
        super().__init__(**kwargs)
        self.agent = SocioPsiAgent()
        self.agent.tui = self

    async def on_mount(self) -> None:
        """Start agent when app mounts."""
        await super().on_mount()
        asyncio.create_task(self.agent.start())

    def action_quit(self) -> None:
        """Stop agent before quitting."""
        self.agent.stop()
        super().action_quit()


def main() -> None:
    """Run Socio-Psi."""
    app = SocioPsiApp()
    app.run()


if __name__ == "__main__":
    main()

"""Entry point for Socio-Psi."""

from sociopsi.presentation.tui import SocioPsiTUI


def main() -> None:
    """Run Socio-Psi."""
    app = SocioPsiTUI()
    app.run()


if __name__ == "__main__":
    main()

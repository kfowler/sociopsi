"""UX rendering abstraction for Socio-Psi output."""

from sociopsi.ux.base import UXRenderer
from sociopsi.ux.console import ConsoleRenderer
from sociopsi.ux.voice import VoiceRenderer

__all__ = ["UXRenderer", "ConsoleRenderer", "VoiceRenderer"]


def _lazy_web_imports() -> tuple[type, type]:
    """Import WebRenderer and WebSocketUXServer on demand.

    The ``websockets`` package is an optional dependency.  Importing at
    module level would force it on every user, so we defer.
    """
    from sociopsi.ux.server import WebSocketUXServer
    from sociopsi.ux.web import WebRenderer

    return WebRenderer, WebSocketUXServer


def get_web_renderer_classes() -> tuple[type, type]:
    """Return ``(WebRenderer, WebSocketUXServer)`` or raise ``ImportError``."""
    return _lazy_web_imports()

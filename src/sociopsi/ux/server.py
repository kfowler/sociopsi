"""Lightweight async WebSocket server for streaming UX state."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

try:
    import websockets
    from websockets.asyncio.server import Server, ServerConnection, serve
except ImportError as _exc:
    raise ImportError(
        "WebSocket support requires the 'websockets' package. "
        "Install it with: pip install sociopsi[web]"
    ) from _exc

logger = logging.getLogger(__name__)


class WebSocketUXServer:
    """Manages WebSocket connections and broadcasts JSON messages.

    Designed to run alongside the agent's asyncio event loop.  Call
    :meth:`start` once, then :meth:`broadcast` from any render method.
    Multiple clients can connect simultaneously.
    """

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: set[ServerConnection] = set()
        self._server: Server | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server (non-blocking)."""
        self._server = await serve(self._handler, self.host, self.port)
        logger.info("WebSocket UX server listening on ws://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Gracefully shut down the server and disconnect all clients."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._clients.clear()
            logger.info("WebSocket UX server stopped")

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    def broadcast(self, msg_type: str, data: dict[str, Any]) -> None:
        """Queue a JSON message to all connected clients.

        Safe to call from synchronous code — schedules the send on the
        running event loop.
        """
        if not self._clients:
            return
        payload = json.dumps({"type": msg_type, "data": data})
        loop = asyncio.get_event_loop()
        for client in set(self._clients):
            loop.create_task(self._safe_send(client, payload))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _handler(self, connection: ServerConnection) -> None:
        """Handle a new WebSocket client connection."""
        self._clients.add(connection)
        remote = connection.remote_address
        logger.info("WebSocket client connected: %s", remote)
        try:
            async for _message in connection:
                pass  # We only broadcast; ignore incoming messages
        finally:
            self._clients.discard(connection)
            logger.info("WebSocket client disconnected: %s", remote)

    async def _safe_send(self, client: ServerConnection, payload: str) -> None:
        """Send a payload, removing the client on failure."""
        try:
            await client.send(payload)
        except websockets.ConnectionClosed:
            self._clients.discard(client)
        except Exception:
            self._clients.discard(client)
            logger.debug("Failed to send to client, removed", exc_info=True)

    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._clients)

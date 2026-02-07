"""WebSocket bridge for real-time archetype event streaming.

Bridges the internal EventBus to external WebSocket clients, allowing
live monitoring of archetype dialogue, ego harmony, and other psyche
events. Clients subscribe to specific channels to receive filtered events.

Channels correspond to event_bus event type prefixes:
    - "dialogue"      → dialogue.archetype_voice, dialogue.complete, etc.
    - "somatic"       → somatic.update
    - "survival"      → survival.battery_critical, survival.thermal_critical
    - "metacognition" → metacognition.reflection
    - "*"             → all events

Includes ping/pong heartbeat for connection health monitoring.
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.server import Server, ServerConnection

from sociopsi.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)

# Events the bridge subscribes to on the internal EventBus.
_BRIDGED_EVENTS = (
    "dialogue.archetype_voice",
    "dialogue.complete",
    "dialogue.command_processed",
    "dialogue.goal_selected",
    "metacognition.reflection",
    "somatic.update",
    "survival.battery_critical",
    "survival.thermal_critical",
)

# Default heartbeat interval (seconds) for WebSocket ping/pong.
_HEARTBEAT_INTERVAL = 20


def _serialize_event(event_type: str, data: dict[str, Any]) -> str:
    """Serialize an event for WebSocket transmission.

    Converts non-JSON-serializable values (dataclasses, enums, etc.) to
    strings so the payload is always valid JSON.
    """

    def _default(obj: object) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict

            return asdict(obj)  # type: ignore[arg-type]
        if hasattr(obj, "value"):  # Enum
            return obj.value
        return str(obj)

    return json.dumps({"type": event_type, "data": data}, default=_default)


@dataclass
class _Client:
    """A connected WebSocket client and its channel subscriptions."""

    ws: ServerConnection
    channels: set[str] = field(default_factory=lambda: {"*"})


class WebSocketBridge:
    """Bridges the internal EventBus to WebSocket clients.

    Usage::

        bridge = WebSocketBridge(host="localhost", port=8765)
        bridge.start()   # non-blocking, spawns background thread
        # ... agent runs ...
        bridge.stop()     # graceful shutdown

    Clients connect and optionally send a JSON subscribe message::

        {"action": "subscribe", "channels": ["dialogue", "somatic"]}

    If no subscribe message is sent, the client receives all events ("*").
    Clients can also unsubscribe::

        {"action": "unsubscribe", "channels": ["somatic"]}
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        event_bus: EventBus | None = None,
        heartbeat_interval: float = _HEARTBEAT_INTERVAL,
    ) -> None:
        self._host = host
        self._port = port
        self._bus = event_bus or get_event_bus()
        self._heartbeat_interval = heartbeat_interval

        self._clients: dict[int, _Client] = {}  # id(ws) → _Client
        self._lock = threading.Lock()  # guards _clients

        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Server | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the WebSocket server in a background thread."""
        if self._thread is not None:
            return

        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(ready,),
            daemon=True,
            name="ws-bridge",
        )
        self._thread.start()
        ready.wait(timeout=5.0)

        # Subscribe to internal events
        for event_type in _BRIDGED_EVENTS:
            self._bus.subscribe(event_type, self._make_handler(event_type))

        logger.info("WebSocket bridge started on ws://%s:%d", self._host, self._port)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the WebSocket server and unsubscribe from events."""
        for event_type in _BRIDGED_EVENTS:
            self._bus.unsubscribe(event_type, self._make_handler(event_type))

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

        self._loop = None
        self._server = None
        logger.info("WebSocket bridge stopped")

    @property
    def port(self) -> int:
        """Actual port the server is listening on (useful when port=0)."""
        return self._port

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    # ------------------------------------------------------------------
    # Internal: asyncio event loop in background thread
    # ------------------------------------------------------------------

    def _run_loop(self, ready: threading.Event) -> None:
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_server(ready))
            self._loop.run_forever()
        finally:
            # Clean shutdown
            if self._server is not None:
                self._server.close()
                self._loop.run_until_complete(
                    asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
                )
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def _start_server(self, ready: threading.Event) -> None:
        """Create and start the WebSocket server."""
        self._server = await websockets.serve(
            self._handle_client,
            self._host,
            self._port,
            ping_interval=self._heartbeat_interval,
            ping_timeout=self._heartbeat_interval,
        )
        # Resolve actual port (when port=0 for tests)
        if self._server is not None:
            for sock in self._server.sockets:
                addr = sock.getsockname()
                self._port = addr[1]
                break
        ready.set()

    # ------------------------------------------------------------------
    # Internal: per-client WebSocket handler
    # ------------------------------------------------------------------

    async def _handle_client(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        client = _Client(ws=ws)
        client_id = id(ws)

        with self._lock:
            self._clients[client_id] = client

        logger.debug("WebSocket client connected (id=%d)", client_id)

        try:
            async for raw_message in ws:
                self._process_client_message(client, raw_message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            with self._lock:
                self._clients.pop(client_id, None)
            logger.debug("WebSocket client disconnected (id=%d)", client_id)

    def _process_client_message(self, client: _Client, raw: str | bytes) -> None:
        """Process a control message from a client (subscribe/unsubscribe)."""
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        action = msg.get("action")
        channels = msg.get("channels")

        if not isinstance(channels, list):
            return

        if action == "subscribe":
            # Subscribing to specific channels replaces the wildcard default
            client.channels.discard("*")
            client.channels.update(channels)
        elif action == "unsubscribe":
            client.channels -= set(channels)
            # If no channels remain, restore wildcard
            if not client.channels:
                client.channels.add("*")

    # ------------------------------------------------------------------
    # Internal: bridge EventBus → WebSocket clients
    # ------------------------------------------------------------------

    def _make_handler(self, event_type: str) -> Any:
        """Create a handler closure for a specific event type.

        We cache handler references so unsubscribe can find them.
        """
        if not hasattr(self, "_handlers"):
            self._handlers: dict[str, Any] = {}

        if event_type not in self._handlers:

            def handler(data: dict[str, Any]) -> None:
                self._broadcast(event_type, data)

            self._handlers[event_type] = handler

        return self._handlers[event_type]

    def _broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event to all matching WebSocket clients."""
        if self._loop is None:
            return

        channel = event_type.split(".")[0]  # "dialogue.complete" → "dialogue"
        message = _serialize_event(event_type, data)

        with self._lock:
            targets = [
                c.ws
                for c in self._clients.values()
                if "*" in c.channels or channel in c.channels
            ]

        if not targets:
            return

        # Schedule sends on the asyncio loop from the EventBus thread
        for ws in targets:
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, message), self._loop)

    @staticmethod
    async def _safe_send(ws: ServerConnection, message: str) -> None:
        """Send a message, ignoring connection errors."""
        try:
            await ws.send(message)
        except (websockets.exceptions.ConnectionClosed, RuntimeError):
            pass

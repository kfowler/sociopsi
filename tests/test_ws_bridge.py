"""Tests for the WebSocket bridge."""

import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from sociopsi.event_bus import EventBus
from sociopsi.ws_bridge import WebSocketBridge, _serialize_event


@pytest.fixture(autouse=True)
def _reset_bus():
    """Reset the singleton before and after each test."""
    EventBus.reset()
    yield
    EventBus.reset()


@pytest.fixture
def bus() -> EventBus:
    bus = EventBus()
    bus.start()
    yield bus
    bus.stop()


@pytest.fixture
def bridge(bus: EventBus):
    """Create a bridge on an ephemeral port, stop it after the test."""
    b = WebSocketBridge(host="localhost", port=0, event_bus=bus)
    b.start()
    yield b
    b.stop()


def ws_url(bridge: WebSocketBridge) -> str:
    return f"ws://localhost:{bridge.port}"


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


class TestSerialize:
    def test_basic_event(self):
        result = json.loads(_serialize_event("test.event", {"key": "value"}))
        assert result["type"] == "test.event"
        assert result["data"]["key"] == "value"

    def test_enum_serialization(self):
        from sociopsi.types import ThermalState

        result = json.loads(
            _serialize_event("somatic.update", {"thermal": ThermalState.COOL})
        )
        assert result["data"]["thermal"] == "cool"

    def test_empty_data(self):
        result = json.loads(_serialize_event("test.event", {}))
        assert result["data"] == {}


# ------------------------------------------------------------------
# Server lifecycle
# ------------------------------------------------------------------


class TestLifecycle:
    def test_start_stop(self, bus: EventBus):
        bridge = WebSocketBridge(host="localhost", port=0, event_bus=bus)
        bridge.start()
        assert bridge.port > 0
        bridge.stop()

    def test_double_start_is_noop(self, bridge: WebSocketBridge):
        port_before = bridge.port
        bridge.start()  # second call
        assert bridge.port == port_before

    def test_client_count_starts_at_zero(self, bridge: WebSocketBridge):
        assert bridge.client_count == 0


# ------------------------------------------------------------------
# Client connections
# ------------------------------------------------------------------


class TestConnections:
    def test_client_connect_and_disconnect(self, bridge: WebSocketBridge):
        async def _run():
            async with connect(ws_url(bridge)):
                # Give the server a moment to register
                await asyncio.sleep(0.05)
                assert bridge.client_count == 1
            # After disconnect
            await asyncio.sleep(0.05)
            assert bridge.client_count == 0

        asyncio.run(_run())

    def test_multiple_clients(self, bridge: WebSocketBridge):
        async def _run():
            async with connect(ws_url(bridge)), connect(ws_url(bridge)):
                await asyncio.sleep(0.05)
                assert bridge.client_count == 2

        asyncio.run(_run())


# ------------------------------------------------------------------
# Event broadcasting
# ------------------------------------------------------------------


class TestBroadcast:
    def test_wildcard_receives_all_events(self, bridge: WebSocketBridge, bus: EventBus):
        """Default client (wildcard) receives events from any channel."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                await asyncio.sleep(0.05)
                bus.publish(
                    "dialogue.archetype_voice",
                    {"archetype": "shadow", "voice": "I feel raw"},
                )
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "dialogue.archetype_voice"
                assert msg["data"]["archetype"] == "shadow"

        asyncio.run(_run())

    def test_subscribed_channel_filter(self, bridge: WebSocketBridge, bus: EventBus):
        """Client subscribed to 'dialogue' only receives dialogue events."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                await ws.send(
                    json.dumps({"action": "subscribe", "channels": ["dialogue"]})
                )
                await asyncio.sleep(0.05)

                # Publish a somatic event (should NOT be received)
                bus.publish("somatic.update", {"battery": 50})
                # Publish a dialogue event (should be received)
                bus.publish(
                    "dialogue.complete",
                    {"harmony": 0.8, "mediated_thought": "All is well"},
                )

                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "dialogue.complete"
                assert msg["data"]["harmony"] == 0.8

        asyncio.run(_run())

    def test_unsubscribe_restores_wildcard(
        self, bridge: WebSocketBridge, bus: EventBus
    ):
        """Unsubscribing all channels restores wildcard."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                # Subscribe to dialogue only
                await ws.send(
                    json.dumps({"action": "subscribe", "channels": ["dialogue"]})
                )
                # Then unsubscribe from everything
                await ws.send(
                    json.dumps({"action": "unsubscribe", "channels": ["dialogue"]})
                )
                await asyncio.sleep(0.05)

                # Now should receive somatic events (wildcard restored)
                bus.publish("somatic.update", {"battery": 42})
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "somatic.update"

        asyncio.run(_run())

    def test_multiple_channels(self, bridge: WebSocketBridge, bus: EventBus):
        """Client can subscribe to multiple channels."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "action": "subscribe",
                            "channels": ["dialogue", "metacognition"],
                        }
                    )
                )
                await asyncio.sleep(0.05)

                bus.publish(
                    "metacognition.reflection",
                    {"reflection": "I notice patterns"},
                )
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                msg = json.loads(raw)
                assert msg["type"] == "metacognition.reflection"

        asyncio.run(_run())

    def test_broadcast_to_multiple_clients(
        self, bridge: WebSocketBridge, bus: EventBus
    ):
        """Event is broadcast to all matching clients."""

        async def _run():
            async with connect(ws_url(bridge)) as ws1, connect(
                ws_url(bridge)
            ) as ws2:
                await asyncio.sleep(0.05)

                bus.publish(
                    "dialogue.archetype_voice",
                    {"archetype": "anima", "voice": "Consider this"},
                )

                raw1 = await asyncio.wait_for(ws1.recv(), timeout=2.0)
                raw2 = await asyncio.wait_for(ws2.recv(), timeout=2.0)
                assert json.loads(raw1)["type"] == "dialogue.archetype_voice"
                assert json.loads(raw2)["type"] == "dialogue.archetype_voice"

        asyncio.run(_run())


# ------------------------------------------------------------------
# Heartbeat (ping/pong handled by websockets library)
# ------------------------------------------------------------------


class TestHeartbeat:
    def test_connection_stays_alive(self, bus: EventBus):
        """With a fast heartbeat, connection survives idle period."""
        bridge = WebSocketBridge(
            host="localhost", port=0, event_bus=bus, heartbeat_interval=1
        )
        bridge.start()
        try:

            async def _run():
                async with connect(ws_url(bridge)) as ws:
                    # Idle for longer than heartbeat interval
                    await asyncio.sleep(1.5)
                    # Connection should still be open
                    bus.publish("dialogue.complete", {"harmony": 0.5})
                    raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    assert json.loads(raw)["type"] == "dialogue.complete"

            asyncio.run(_run())
        finally:
            bridge.stop()


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_invalid_json_from_client(self, bridge: WebSocketBridge, bus: EventBus):
        """Invalid JSON from client doesn't crash the server."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                await ws.send("not json at all")
                await asyncio.sleep(0.05)
                # Server still works - publish and receive
                bus.publish("dialogue.complete", {"harmony": 0.6})
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                assert json.loads(raw)["type"] == "dialogue.complete"

        asyncio.run(_run())

    def test_subscribe_with_bad_channels_type(
        self, bridge: WebSocketBridge, bus: EventBus
    ):
        """Non-list channels value is ignored."""

        async def _run():
            async with connect(ws_url(bridge)) as ws:
                await ws.send(
                    json.dumps({"action": "subscribe", "channels": "not_a_list"})
                )
                await asyncio.sleep(0.05)
                # Still on wildcard, should receive everything
                bus.publish("somatic.update", {"battery": 99})
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                assert json.loads(raw)["type"] == "somatic.update"

        asyncio.run(_run())

    def test_broadcast_after_client_disconnect(
        self, bridge: WebSocketBridge, bus: EventBus
    ):
        """Broadcasting after a client disconnects doesn't raise."""

        async def _run():
            ws = await connect(ws_url(bridge))
            await asyncio.sleep(0.05)
            await ws.close()
            await asyncio.sleep(0.05)
            # This should not raise
            bus.publish("dialogue.complete", {"harmony": 0.5})
            await asyncio.sleep(0.1)

        asyncio.run(_run())

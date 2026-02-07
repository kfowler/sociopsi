"""Tests for WebRenderer and WebSocketUXServer."""

from __future__ import annotations

from datetime import datetime

import pytest

from sociopsi.types import (
    Action,
    ActionResult,
    Event,
    LidState,
    NetworkState,
    PowerState,
    SomaticState,
    StreamSegment,
    ThermalState,
)
from sociopsi.ux.web import WebRenderer


def _make_somatic(**kwargs: object) -> SomaticState:
    defaults = dict(
        battery_percent=80,
        battery_health=95,
        battery_cycles=200,
        power_state=PowerState.AC,
        cpu_percent=25,
        gpu_percent=10,
        thermal_state=ThermalState.COOL,
        thermal_cpu=45.0,
        thermal_gpu=40.0,
        ram_percent=50,
        storage_percent=60,
        network_state=NetworkState.CONNECTED,
        lid_state=LidState.OPEN,
        fan_rpm=0,
        uptime_seconds=3600,
    )
    defaults.update(kwargs)
    return SomaticState(**defaults)


class FakeServer:
    """Records broadcast calls for assertion."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    def broadcast(self, msg_type: str, data: dict) -> None:
        self.messages.append((msg_type, data))

    @property
    def last(self) -> tuple[str, dict]:
        return self.messages[-1]


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()


@pytest.fixture
def renderer(server: FakeServer) -> WebRenderer:
    return WebRenderer(server)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------------


class TestWebRendererStartup:
    def test_sends_startup_config(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_startup({"model": "test", "mode": "web"})
        assert server.last == ("startup", {"config": {"model": "test", "mode": "web"}})


class TestWebRendererShutdown:
    def test_sends_shutdown_message(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_shutdown("Goodbye!")
        assert server.last == ("shutdown", {"message": "Goodbye!"})


# ------------------------------------------------------------------
# Cycle
# ------------------------------------------------------------------


class TestWebRendererCycleHeader:
    def test_sends_cycle_info(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_cycle_header(42, "2026-02-06 12:00:00")
        msg_type, data = server.last
        assert msg_type == "cycle_header"
        assert data["cycle"] == 42
        assert data["timestamp"] == "2026-02-06 12:00:00"


# ------------------------------------------------------------------
# Perception
# ------------------------------------------------------------------


class TestWebRendererSomatic:
    def test_serialises_all_somatic_fields(self, renderer: WebRenderer, server: FakeServer) -> None:
        somatic = _make_somatic(battery_percent=75, cpu_percent=30)
        renderer.render_somatic(somatic)
        msg_type, data = server.last
        assert msg_type == "somatic"
        assert data["battery_percent"] == 75
        assert data["cpu_percent"] == 30
        assert data["power_state"] == "ac"
        assert data["thermal_state"] == "cool"
        assert data["network_state"] == "connected"
        assert data["lid_state"] == "open"
        assert "tag" in data


class TestWebRendererDrives:
    def test_sends_drive_text(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_drives("[DRIVES]\n  curiosity 0.70")
        assert server.last == ("drives", {"text": "[DRIVES]\n  curiosity 0.70"})


class TestWebRendererModulators:
    def test_sends_modulator_text(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_modulators("[MODULATORS]\n  dopamine 0.50")
        assert server.last == ("modulators", {"text": "[MODULATORS]\n  dopamine 0.50"})


class TestWebRendererPlanning:
    def test_sends_planning_text(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_planning("[PLANNING]\n  Goal: explore")
        assert server.last == ("planning", {"text": "[PLANNING]\n  Goal: explore"})


class TestWebRendererEvents:
    def test_serialises_events(self, renderer: WebRenderer, server: FakeServer) -> None:
        ts = datetime(2026, 2, 6, 12, 0, 0)
        events = [Event(type="app_change", description="Switched to Terminal", timestamp=ts)]
        renderer.render_events(events)
        msg_type, data = server.last
        assert msg_type == "events"
        assert len(data["events"]) == 1
        evt = data["events"][0]
        assert evt["type"] == "app_change"
        assert evt["description"] == "Switched to Terminal"
        assert evt["timestamp"] == ts.isoformat()


# ------------------------------------------------------------------
# Inner life
# ------------------------------------------------------------------


class TestWebRendererStream:
    def test_serialises_segments(self, renderer: WebRenderer, server: FakeServer) -> None:
        segments = [
            StreamSegment(component="shadow", text="Fear."),
            StreamSegment(component="anima", text="Peaceful."),
        ]
        renderer.render_stream(segments)
        msg_type, data = server.last
        assert msg_type == "stream"
        assert len(data["segments"]) == 2
        assert data["segments"][0] == {"component": "shadow", "text": "Fear."}
        assert data["segments"][1] == {"component": "anima", "text": "Peaceful."}


class TestWebRendererEgo:
    def test_sends_ego_data(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_ego("A thought", 0.75, 0.82)
        msg_type, data = server.last
        assert msg_type == "ego"
        assert data["mediated_thought"] == "A thought"
        assert data["harmony"] == 0.75
        assert data["ego_strength"] == 0.82


class TestWebRendererReflection:
    def test_sends_reflection(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_reflection("I notice my drives are balanced.")
        assert server.last == ("reflection", {"text": "I notice my drives are balanced."})


# ------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------


class TestWebRendererCompulsive:
    def test_sends_compulsive_actions(self, renderer: WebRenderer, server: FakeServer) -> None:
        actions = [Action(type="check_battery")]
        renderer.render_compulsive(actions)
        msg_type, data = server.last
        assert msg_type == "compulsive"
        assert data["actions"] == [{"type": "check_battery", "params": {}}]


class TestWebRendererImpulseInhibition:
    def test_sends_suppressed(self, renderer: WebRenderer, server: FakeServer) -> None:
        suppressed = [Action(type="speak", params={"text": "hi"})]
        renderer.render_impulse_inhibition(suppressed)
        msg_type, data = server.last
        assert msg_type == "impulse_inhibition"
        assert data["suppressed"] == [{"type": "speak", "params": {"text": "hi"}}]


class TestWebRendererActions:
    def test_sends_tagged_actions(self, renderer: WebRenderer, server: FakeServer) -> None:
        compulsive_action = Action(type="check_battery")
        planned_action = Action(type="look")
        primed_action = Action(type="speak", params={"text": "hello"})
        llm_action = Action(type="journal")

        all_actions = [compulsive_action, planned_action, primed_action, llm_action]
        renderer.render_actions(
            all_actions,
            compulsive=[compulsive_action],
            planned=[planned_action],
            primed=[primed_action],
        )
        msg_type, data = server.last
        assert msg_type == "actions"
        actions = data["actions"]
        assert actions[0]["source"] == "compulsive"
        assert actions[1]["source"] == "planned"
        assert actions[2]["source"] == "primed"
        assert actions[3]["source"] == "llm"

    def test_empty_actions(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_actions([], [], [], [])
        msg_type, data = server.last
        assert msg_type == "actions"
        assert data["actions"] == []


class TestWebRendererResults:
    def test_sends_success_result(self, renderer: WebRenderer, server: FakeServer) -> None:
        results = [ActionResult(action_type="look", success=True, result={"scene": "a desk"})]
        renderer.render_results(results)
        msg_type, data = server.last
        assert msg_type == "results"
        assert data["results"][0]["success"] is True
        assert data["results"][0]["result"] == {"scene": "a desk"}

    def test_sends_failure_result(self, renderer: WebRenderer, server: FakeServer) -> None:
        results = [ActionResult(action_type="speak", success=False, error="TTS unavailable")]
        renderer.render_results(results)
        msg_type, data = server.last
        assert data["results"][0]["success"] is False
        assert data["results"][0]["error"] == "TTS unavailable"


# ------------------------------------------------------------------
# Heartbeat
# ------------------------------------------------------------------


class TestWebRendererHeartbeat:
    def test_sends_heartbeat_change(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_heartbeat_change("idle", "active", 1.0)
        assert server.last == ("heartbeat_change", {
            "old_mode": "idle",
            "new_mode": "active",
            "interval": 1.0,
        })


# ------------------------------------------------------------------
# Speech
# ------------------------------------------------------------------


class TestWebRendererSpeech:
    def test_sends_final_speech(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_speech("hello world", is_final=True)
        assert server.last == ("speech", {"text": "hello world", "is_final": True})

    def test_sends_partial_speech(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_speech("hel", is_final=False)
        assert server.last == ("speech", {"text": "hel", "is_final": False})


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------


class TestWebRendererError:
    def test_sends_string_error(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_error("Connection timeout")
        assert server.last == ("error", {"message": "Connection timeout"})

    def test_sends_exception_error(self, renderer: WebRenderer, server: FakeServer) -> None:
        renderer.render_error(RuntimeError("test error"))
        assert server.last == ("error", {"message": "test error"})


# ------------------------------------------------------------------
# WebSocketUXServer unit tests
# ------------------------------------------------------------------


class TestWebSocketUXServer:
    def test_broadcast_no_clients(self) -> None:
        """Broadcast with no clients is a no-op."""
        from sociopsi.ux.server import WebSocketUXServer

        server = WebSocketUXServer()
        # Should not raise
        server.broadcast("test", {"key": "value"})

    def test_client_count_starts_zero(self) -> None:
        from sociopsi.ux.server import WebSocketUXServer

        server = WebSocketUXServer()
        assert server.client_count == 0

    def test_init_defaults(self) -> None:
        from sociopsi.ux.server import WebSocketUXServer

        server = WebSocketUXServer()
        assert server.host == "localhost"
        assert server.port == 8765

    def test_init_custom(self) -> None:
        from sociopsi.ux.server import WebSocketUXServer

        server = WebSocketUXServer(host="0.0.0.0", port=9999)
        assert server.host == "0.0.0.0"
        assert server.port == 9999


# ------------------------------------------------------------------
# Integration: WebRenderer is a UXRenderer
# ------------------------------------------------------------------


class TestWebRendererIsUXRenderer:
    def test_isinstance(self, renderer: WebRenderer) -> None:
        from sociopsi.ux.base import UXRenderer

        assert isinstance(renderer, UXRenderer)

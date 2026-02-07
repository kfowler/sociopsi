"""WebRenderer — streams agent state as JSON over WebSocket."""

from __future__ import annotations

from typing import Any

from sociopsi.types import Action, ActionResult, Event, SomaticState, StreamSegment
from sociopsi.ux.base import UXRenderer
from sociopsi.ux.server import WebSocketUXServer


class WebRenderer(UXRenderer):
    """Streams each render call as a typed JSON message over WebSocket.

    Each method serialises its arguments into a ``{type, data}`` envelope
    and broadcasts to all connected WebSocket clients via the server.
    """

    def __init__(self, server: WebSocketUXServer) -> None:
        self._server = server

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send(self, msg_type: str, data: dict[str, Any]) -> None:
        self._server.broadcast(msg_type, data)

    @staticmethod
    def _action_to_dict(action: Action) -> dict[str, Any]:
        return {"type": action.type, "params": action.params}

    @staticmethod
    def _result_to_dict(result: ActionResult) -> dict[str, Any]:
        d: dict[str, Any] = {
            "action_type": result.action_type,
            "success": result.success,
        }
        if result.success and result.result is not None:
            d["result"] = result.result
        if not result.success and result.error:
            d["error"] = result.error
        return d

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def render_startup(self, config_summary: dict[str, Any]) -> None:
        self._send("startup", {"config": config_summary})

    def render_shutdown(self, message: str) -> None:
        self._send("shutdown", {"message": message})

    # ------------------------------------------------------------------
    # Cycle framing
    # ------------------------------------------------------------------

    def render_cycle_header(self, cycle_count: int, timestamp: str) -> None:
        self._send("cycle_header", {"cycle": cycle_count, "timestamp": timestamp})

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    def render_somatic(self, somatic: SomaticState) -> None:
        self._send("somatic", {
            "battery_percent": somatic.battery_percent,
            "battery_health": somatic.battery_health,
            "battery_cycles": somatic.battery_cycles,
            "power_state": somatic.power_state.value,
            "cpu_percent": somatic.cpu_percent,
            "gpu_percent": somatic.gpu_percent,
            "thermal_state": somatic.thermal_state.value,
            "thermal_cpu": somatic.thermal_cpu,
            "thermal_gpu": somatic.thermal_gpu,
            "ram_percent": somatic.ram_percent,
            "storage_percent": somatic.storage_percent,
            "network_state": somatic.network_state.value,
            "lid_state": somatic.lid_state.value,
            "fan_rpm": somatic.fan_rpm,
            "uptime_seconds": somatic.uptime_seconds,
            "tag": somatic.to_tag(),
        })

    def render_drives(self, drive_text: str) -> None:
        self._send("drives", {"text": drive_text})

    def render_modulators(self, modulator_text: str) -> None:
        self._send("modulators", {"text": modulator_text})

    def render_planning(self, goals_text: str) -> None:
        self._send("planning", {"text": goals_text})

    def render_events(self, events: list[Event]) -> None:
        self._send("events", {
            "events": [
                {
                    "type": e.type,
                    "description": e.description,
                    "timestamp": e.timestamp.isoformat(),
                    "data": e.data,
                }
                for e in events
            ]
        })

    # ------------------------------------------------------------------
    # Inner life
    # ------------------------------------------------------------------

    def render_stream(self, segments: list[StreamSegment]) -> None:
        self._send("stream", {
            "segments": [
                {"component": s.component, "text": s.text}
                for s in segments
            ]
        })

    def render_ego(self, mediated_thought: str, harmony: float, ego_strength: float) -> None:
        self._send("ego", {
            "mediated_thought": mediated_thought,
            "harmony": harmony,
            "ego_strength": ego_strength,
        })

    def render_reflection(self, reflection_text: str) -> None:
        self._send("reflection", {"text": reflection_text})

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def render_compulsive(self, actions: list[Action]) -> None:
        self._send("compulsive", {
            "actions": [self._action_to_dict(a) for a in actions],
        })

    def render_impulse_inhibition(self, suppressed: list[Action]) -> None:
        self._send("impulse_inhibition", {
            "suppressed": [self._action_to_dict(a) for a in suppressed],
        })

    def render_actions(
        self,
        actions: list[Action],
        compulsive: list[Action],
        planned: list[Action],
        primed: list[Action],
    ) -> None:
        def _tagged(action: Action) -> dict[str, Any]:
            d = self._action_to_dict(action)
            if action in compulsive:
                d["source"] = "compulsive"
            elif action in planned:
                d["source"] = "planned"
            elif action in primed:
                d["source"] = "primed"
            else:
                d["source"] = "llm"
            return d

        self._send("actions", {
            "actions": [_tagged(a) for a in actions],
        })

    def render_results(self, results: list[ActionResult]) -> None:
        self._send("results", {
            "results": [self._result_to_dict(r) for r in results],
        })

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def render_heartbeat_change(
        self, old_mode: str, new_mode: str, interval: float
    ) -> None:
        self._send("heartbeat_change", {
            "old_mode": old_mode,
            "new_mode": new_mode,
            "interval": interval,
        })

    # ------------------------------------------------------------------
    # Speech
    # ------------------------------------------------------------------

    def render_speech(self, text: str, is_final: bool) -> None:
        self._send("speech", {"text": text, "is_final": is_final})

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    def render_error(self, error: str | Exception) -> None:
        self._send("error", {"message": str(error)})

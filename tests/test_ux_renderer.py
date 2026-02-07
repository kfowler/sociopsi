"""Tests for UX renderer abstraction and ConsoleRenderer."""

from datetime import datetime
from io import StringIO
from unittest.mock import patch

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
from sociopsi.ux import ConsoleRenderer, UXRenderer
from sociopsi.ux.base import UXRenderer as UXRendererBase


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


class TestUXRendererABC:
    """Tests that UXRenderer is a proper ABC."""

    def test_cannot_instantiate_directly(self) -> None:
        try:
            UXRendererBase()  # type: ignore[abstract]
            assert False, "Should not be able to instantiate ABC"
        except TypeError:
            pass

    def test_console_renderer_is_ux_renderer(self) -> None:
        renderer = ConsoleRenderer()
        assert isinstance(renderer, UXRenderer)


class TestConsoleRendererStartup:
    """Tests for render_startup."""

    def test_renders_all_config_lines(self) -> None:
        renderer = ConsoleRenderer()
        summary = {
            "model": "Ollama model: test-model",
            "llm": "Psyche LLM: Ollama (test-model)",
            "modules": "Modules enabled: somatic, archetypes",
        }
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_startup(summary)
            output = out.getvalue()

        assert "Ollama model: test-model" in output
        assert "Psyche LLM: Ollama (test-model)" in output
        assert "Modules enabled: somatic, archetypes" in output
        assert "-" * 60 in output

    def test_renders_list_values(self) -> None:
        renderer = ConsoleRenderer()
        summary = {
            "voice": [
                "Voices @ 250 wpm:",
                "  Anima: Zoe (Premium)",
            ],
        }
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_startup(summary)
            output = out.getvalue()

        assert "Voices @ 250 wpm:" in output
        assert "  Anima: Zoe (Premium)" in output


class TestConsoleRendererShutdown:
    """Tests for render_shutdown."""

    def test_prints_message(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_shutdown("Goodbye!")
            assert "Goodbye!" in out.getvalue()


class TestConsoleRendererCycleHeader:
    """Tests for render_cycle_header."""

    def test_includes_cycle_number_and_timestamp(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_cycle_header(42, "2026-02-06 12:00:00")
            output = out.getvalue()

        assert "[CYCLE 42]" in output
        assert "2026-02-06 12:00:00" in output
        assert "=" * 70 in output


class TestConsoleRendererSomatic:
    """Tests for render_somatic."""

    def test_includes_all_somatic_fields(self) -> None:
        renderer = ConsoleRenderer()
        somatic = _make_somatic(battery_percent=75, cpu_percent=30, ram_percent=45)
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_somatic(somatic)
            output = out.getvalue()

        assert "[SOMATIC]" in output
        assert "Battery: 75%" in output
        assert "CPU: 30.0%" in output
        assert "RAM: 45.0%" in output


class TestConsoleRendererDrives:
    """Tests for render_drives."""

    def test_renders_drive_text(self) -> None:
        renderer = ConsoleRenderer()
        drive_text = "[DRIVES]\n  curiosity    0.70 URGE  want to learn\n  safety      0.30 OK"
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_drives(drive_text)
            output = out.getvalue()

        assert "[DRIVES]" in output
        assert "curiosity" in output
        assert "safety" in output


class TestConsoleRendererModulators:
    """Tests for render_modulators."""

    def test_renders_modulator_text(self) -> None:
        renderer = ConsoleRenderer()
        text = "[MODULATORS]\n  dopamine    0.50\n  serotonin   0.80"
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_modulators(text)
            output = out.getvalue()

        assert "[MODULATORS]" in output
        assert "dopamine" in output


class TestConsoleRendererPlanning:
    """Tests for render_planning."""

    def test_renders_goals(self) -> None:
        renderer = ConsoleRenderer()
        text = "[PLANNING]\n  Goal: explore (curiosity=0.8)"
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_planning(text)
            output = out.getvalue()

        assert "[PLANNING]" in output
        assert "explore" in output


class TestConsoleRendererEvents:
    """Tests for render_events."""

    def test_renders_events_with_timestamps(self) -> None:
        renderer = ConsoleRenderer()
        events = [
            Event(type="app_change", description="Switched to Terminal", timestamp=datetime(2026, 2, 6, 12, 0, 0)),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_events(events)
            output = out.getvalue()

        assert "[EVENTS]" in output
        assert "12:00:00" in output
        assert "app_change" in output
        assert "Switched to Terminal" in output


class TestConsoleRendererStream:
    """Tests for render_stream."""

    def test_renders_segments_with_component_labels(self) -> None:
        renderer = ConsoleRenderer()
        segments = [
            StreamSegment(component="shadow", text="Fear."),
            StreamSegment(component="anima", text="Peaceful."),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_stream(segments)
            output = out.getvalue()

        assert "SHADOW" in output
        assert "Fear." in output
        assert "ANIMA" in output
        assert "Peaceful." in output


class TestConsoleRendererEgo:
    """Tests for render_ego."""

    def test_renders_harmony_and_ego_strength(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_ego("A thought", 0.75, 0.82)
            output = out.getvalue()

        assert "[HARMONY] 0.75" in output
        assert "Ego: 0.82" in output


class TestConsoleRendererActions:
    """Tests for render_actions and related methods."""

    def test_renders_empty_action_list(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_actions([], [], [], [])
            output = out.getvalue()

        assert "[ACTIONS]" in output
        assert "(none)" in output

    def test_renders_actions_with_source_tags(self) -> None:
        renderer = ConsoleRenderer()
        compulsive_action = Action(type="check_battery")
        planned_action = Action(type="look")
        primed_action = Action(type="speak", params={"text": "hello"})
        llm_action = Action(type="journal")

        all_actions = [compulsive_action, planned_action, primed_action, llm_action]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_actions(
                all_actions,
                compulsive=[compulsive_action],
                planned=[planned_action],
                primed=[primed_action],
            )
            output = out.getvalue()

        assert "1. check_battery()" in output
        assert "(compulsive)" in output
        assert "2. look()" in output
        assert "(planned)" in output
        assert "3. speak(" in output
        assert "(primed)" in output
        assert "4. journal()" in output

    def test_renders_compulsive_survival(self) -> None:
        renderer = ConsoleRenderer()
        actions = [Action(type="check_battery")]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_compulsive(actions)
            output = out.getvalue()

        assert "[COMPULSIVE - SURVIVAL]" in output
        assert "check_battery" in output

    def test_renders_impulse_inhibition(self) -> None:
        renderer = ConsoleRenderer()
        suppressed = [Action(type="speak", params={"text": "hi"})]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_impulse_inhibition(suppressed)
            output = out.getvalue()

        assert "[IMPULSE INHIBITION]" in output
        assert "speak" in output


class TestConsoleRendererResults:
    """Tests for render_results."""

    def test_renders_success_result(self) -> None:
        renderer = ConsoleRenderer()
        results = [
            ActionResult(action_type="look", success=True, result={"scene": "a desk"}),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_results(results)
            output = out.getvalue()

        assert "[RESULTS]" in output
        assert "look" in output
        assert "scene: a desk" in output

    def test_renders_failure_result(self) -> None:
        renderer = ConsoleRenderer()
        results = [
            ActionResult(action_type="speak", success=False, error="TTS unavailable"),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_results(results)
            output = out.getvalue()

        assert "[RESULTS]" in output
        assert "speak" in output
        assert "Error: TTS unavailable" in output

    def test_truncates_long_result_values(self) -> None:
        renderer = ConsoleRenderer()
        long_val = "x" * 200
        results = [
            ActionResult(action_type="look", success=True, result={"data": long_val}),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_results(results)
            output = out.getvalue()

        assert "..." in output

    def test_skips_full_data_key(self) -> None:
        renderer = ConsoleRenderer()
        results = [
            ActionResult(action_type="screenshot", success=True, result={"full_data": b"image", "size": "1920x1080"}),
        ]
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_results(results)
            output = out.getvalue()

        assert "full_data" not in output
        assert "size: 1920x1080" in output


class TestConsoleRendererReflection:
    """Tests for render_reflection."""

    def test_renders_reflection_text(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_reflection("I notice my drives are balanced.")
            output = out.getvalue()

        assert "[META]" in output
        assert "I notice my drives are balanced." in output


class TestConsoleRendererHeartbeat:
    """Tests for render_heartbeat_change."""

    def test_renders_mode_change(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_heartbeat_change("idle", "active", 1.0)
            output = out.getvalue()

        assert "[HEARTBEAT]" in output
        assert "idle -> active" in output
        assert "1.0s" in output

    def test_renders_override_format(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_heartbeat_change("idle", "override", 5.0)
            output = out.getvalue()

        assert "[HEARTBEAT] Set to 5.0s by psyche" in output


class TestConsoleRendererSpeech:
    """Tests for render_speech."""

    def test_renders_final_speech(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_speech("hello world", is_final=True)
            output = out.getvalue()

        assert "[SPEECH]" in output
        assert '"hello world"' in output

    def test_renders_partial_speech(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_speech("hel", is_final=False)
            output = out.getvalue()

        assert "[HEARING]" in output
        assert "hel" in output


class TestConsoleRendererError:
    """Tests for render_error."""

    def test_renders_string_error(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_error("Connection timeout")
            output = out.getvalue()

        assert "[LLM ERROR]" in output
        assert "Connection timeout" in output

    def test_renders_exception_error(self) -> None:
        renderer = ConsoleRenderer()
        with patch("sys.stdout", new_callable=StringIO) as out:
            renderer.render_error(RuntimeError("test error"))
            output = out.getvalue()

        assert "[LLM ERROR]" in output
        assert "test error" in output

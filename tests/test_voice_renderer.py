"""Tests for VoiceRenderer speech-only headless output."""

from unittest.mock import MagicMock, call

from sociopsi.platform.base import AudioBackend
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
from sociopsi.ux import VoiceRenderer
from sociopsi.ux.base import UXRenderer


def _make_audio(**overrides: object) -> MagicMock:
    """Create a mock AudioBackend."""
    mock = MagicMock(spec=AudioBackend)
    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock


def _make_somatic(**kwargs: object) -> SomaticState:
    defaults = {
        "battery_percent": 80,
        "battery_health": 95,
        "battery_cycles": 200,
        "power_state": PowerState.AC,
        "cpu_percent": 25,
        "gpu_percent": 10,
        "thermal_state": ThermalState.COOL,
        "thermal_cpu": 45.0,
        "thermal_gpu": 40.0,
        "ram_percent": 50,
        "storage_percent": 60,
        "network_state": NetworkState.CONNECTED,
        "lid_state": LidState.OPEN,
        "fan_rpm": 0,
        "uptime_seconds": 3600,
    }
    defaults.update(kwargs)
    return SomaticState(**defaults)


class TestVoiceRendererIsUXRenderer:
    def test_is_ux_renderer(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        assert isinstance(renderer, UXRenderer)


class TestVoiceRendererStartupShutdown:
    def test_startup_speaks(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_startup({"model": "test"})
        audio.speak.assert_called_once_with("Starting up.", voice=None, rate=200)

    def test_shutdown_speaks_message(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_shutdown("Goodbye!")
        audio.speak.assert_called_once_with("Goodbye!", voice=None, rate=200)

    def test_custom_voice_and_rate(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio, voice="Zoe", rate=250)
        renderer.render_shutdown("Bye")
        audio.speak.assert_called_once_with("Bye", voice="Zoe", rate=250)


class TestVoiceRendererSilentMethods:
    """Methods that should produce NO speech output."""

    def test_cycle_header_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_cycle_header(1, "2026-02-06")
        audio.speak.assert_not_called()

    def test_heartbeat_change_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_heartbeat_change("idle", "active", 1.0)
        audio.speak.assert_not_called()

    def test_modulators_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_modulators("[MODULATORS]\n  dopamine 0.5")
        audio.speak.assert_not_called()

    def test_planning_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_planning("[PLANNING]\n  Goal: explore")
        audio.speak.assert_not_called()

    def test_events_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_events([Event(type="test", description="test")])
        audio.speak.assert_not_called()

    def test_reflection_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_reflection("I notice my drives are balanced.")
        audio.speak.assert_not_called()

    def test_impulse_inhibition_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_impulse_inhibition([Action(type="speak")])
        audio.speak.assert_not_called()


class TestVoiceRendererSomatic:
    def test_normal_state_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_somatic(_make_somatic())
        audio.speak.assert_not_called()

    def test_low_battery_speaks(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_somatic(_make_somatic(battery_percent=10))
        audio.speak.assert_any_call("Warning: battery at 10 percent.", voice=None, rate=200)

    def test_hot_thermal_speaks(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_somatic(_make_somatic(thermal_state=ThermalState.HOT))
        audio.speak.assert_called_once_with("Warning: thermal state is hot.", voice=None, rate=200)

    def test_critical_thermal_speaks(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_somatic(_make_somatic(thermal_state=ThermalState.CRITICAL))
        audio.speak.assert_called_once_with(
            "Warning: thermal state is critical.", voice=None, rate=200
        )

    def test_low_battery_and_hot_both_speak(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_somatic(
            _make_somatic(battery_percent=5, thermal_state=ThermalState.CRITICAL)
        )
        assert audio.speak.call_count == 2


class TestVoiceRendererDrives:
    def test_low_urgency_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_drives("[DRIVES]\n  curiosity    0.30 OK    all good")
        audio.speak.assert_not_called()

    def test_high_urgency_speaks(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_drives("[DRIVES]\n  curiosity    0.80 URGE  want to learn")
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "Feeling:" in spoken
        assert "want to learn" in spoken

    def test_threshold_not_exceeded_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_drives("[DRIVES]\n  curiosity    0.70 OK    fine")
        audio.speak.assert_not_called()


class TestVoiceRendererStream:
    def test_speaks_all_segments(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        segments = [
            StreamSegment(component="shadow", text="Fear rising."),
            StreamSegment(component="anima", text="Peace within."),
        ]
        renderer.render_stream(segments)
        assert audio.speak.call_count == 2
        calls = audio.speak.call_args_list
        assert calls[0] == call("Shadow says: Fear rising.", voice=None, rate=200)
        assert calls[1] == call("Anima says: Peace within.", voice=None, rate=200)

    def test_unknown_component_uses_raw_name(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        segments = [StreamSegment(component="default", text="Hello.")]
        renderer.render_stream(segments)
        spoken = audio.speak.call_args[0][0]
        assert "default says: Hello." in spoken


class TestVoiceRendererEgo:
    def test_speaks_mediated_thought(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_ego("I should look around.", 0.75, 0.82)
        audio.speak.assert_called_once_with("I should look around.", voice=None, rate=200)

    def test_empty_thought_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_ego("", 0.5, 0.5)
        audio.speak.assert_not_called()


class TestVoiceRendererCompulsive:
    def test_speaks_survival_override(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_compulsive([Action(type="check_battery")])
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "Survival override" in spoken
        assert "check_battery" in spoken

    def test_empty_compulsive_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_compulsive([])
        audio.speak.assert_not_called()


class TestVoiceRendererActions:
    def test_speaks_action_summary(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        actions = [Action(type="look"), Action(type="check_weather")]
        renderer.render_actions(actions, [], [], [])
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "I will" in spoken
        assert "look" in spoken
        assert "check weather" in spoken

    def test_single_action(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_actions([Action(type="look")], [], [], [])
        spoken = audio.speak.call_args[0][0]
        assert spoken == "I will look."

    def test_three_actions_uses_comma_and(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        actions = [Action(type="look"), Action(type="speak"), Action(type="journal")]
        renderer.render_actions(actions, [], [], [])
        spoken = audio.speak.call_args[0][0]
        assert "I will look, speak, and journal." == spoken

    def test_empty_actions_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_actions([], [], [], [])
        audio.speak.assert_not_called()


class TestVoiceRendererResults:
    def test_speaks_perception_result(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        results = [
            ActionResult(action_type="look", success=True, result={"scene": "a dark room"}),
        ]
        renderer.render_results(results)
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "a dark room" in spoken

    def test_skips_full_data_key(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        results = [
            ActionResult(
                action_type="screenshot",
                success=True,
                result={"full_data": "binary", "size": "1920x1080"},
            ),
        ]
        renderer.render_results(results)
        spoken = audio.speak.call_args[0][0]
        assert "full_data" not in spoken
        assert "1920x1080" in spoken

    def test_speaks_error_result(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        results = [
            ActionResult(action_type="speak", success=False, error="TTS unavailable"),
        ]
        renderer.render_results(results)
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "Error" in spoken
        assert "TTS unavailable" in spoken

    def test_routine_success_no_dict_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        results = [
            ActionResult(action_type="journal", success=True, result="ok"),
        ]
        renderer.render_results(results)
        audio.speak.assert_not_called()

    def test_success_with_empty_strings_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        results = [
            ActionResult(action_type="look", success=True, result={"scene": ""}),
        ]
        renderer.render_results(results)
        audio.speak.assert_not_called()


class TestVoiceRendererSpeech:
    def test_final_speech_acknowledged(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_speech("hello world", is_final=True)
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "I heard you say" in spoken
        assert "hello world" in spoken

    def test_partial_speech_silent(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_speech("hel", is_final=False)
        audio.speak.assert_not_called()


class TestVoiceRendererError:
    def test_speaks_string_error(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_error("Connection timeout")
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "Error" in spoken
        assert "Connection timeout" in spoken

    def test_speaks_exception_error(self) -> None:
        audio = _make_audio()
        renderer = VoiceRenderer(audio)
        renderer.render_error(RuntimeError("test error"))
        audio.speak.assert_called_once()
        spoken = audio.speak.call_args[0][0]
        assert "Error" in spoken
        assert "test error" in spoken


class TestVoiceRendererTTSFailure:
    def test_speak_failure_logged_not_raised(self) -> None:
        audio = _make_audio()
        audio.speak.side_effect = RuntimeError("TTS crashed")
        renderer = VoiceRenderer(audio)
        # Should not raise
        renderer.render_error("test")

"""Platform abstraction layer for hardware access.

Detects the current platform and provides the appropriate backends
for power, thermal, display, speech recognition, volume, notification,
clipboard, screenshot, app control, and network management.
"""

import sys

from sociopsi.platform.base import (
    AppBackend,
    AudioBackend,
    BatteryInfo,
    ClipboardBackend,
    DeviceBackend,
    DisplayBackend,
    DisplayInfo,
    NetworkControlBackend,
    NotificationBackend,
    PowerBackend,
    ScreenshotBackend,
    SensorUnavailable,
    ThermalBackend,
    ThermalInfo,
    ThunderboltDevice,
    USBDevice,
    VoiceInfo,
    VolumeBackend,
)
from sociopsi.platform.speech import SpeechBackend


def _detect_platform() -> str:
    """Detect the current platform."""
    if sys.platform == "darwin":
        return "darwin"
    elif sys.platform.startswith("linux"):
        return "linux"
    else:
        return sys.platform


def get_power_backend() -> PowerBackend:
    """Get the power management backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.power import DarwinPowerBackend

        return DarwinPowerBackend()
    elif platform == "linux":
        from sociopsi.platform.power import LinuxPowerBackend

        return LinuxPowerBackend()
    else:
        raise SensorUnavailable(f"No power backend for platform: {platform}")


def get_thermal_backend() -> ThermalBackend:
    """Get the thermal monitoring backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.thermal import DarwinThermalBackend

        return DarwinThermalBackend()
    elif platform == "linux":
        from sociopsi.platform.thermal import LinuxThermalBackend

        return LinuxThermalBackend()
    else:
        raise SensorUnavailable(f"No thermal backend for platform: {platform}")


def get_display_backend() -> DisplayBackend:
    """Get the display management backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.display import DarwinDisplayBackend

        return DarwinDisplayBackend()
    elif platform == "linux":
        from sociopsi.platform.display import LinuxDisplayBackend

        return LinuxDisplayBackend()
    else:
        raise SensorUnavailable(f"No display backend for platform: {platform}")


def get_device_backend() -> DeviceBackend:
    """Get the device enumeration backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.devices import DarwinDeviceBackend

        return DarwinDeviceBackend()
    elif platform == "linux":
        from sociopsi.platform.devices import LinuxDeviceBackend

        return LinuxDeviceBackend()
    else:
        raise SensorUnavailable(f"No device backend for platform: {platform}")


def get_speech_backend(locale: str = "en-US", on_device: bool = True) -> SpeechBackend:
    """Get the speech recognition backend for the current platform.

    Args:
        locale: BCP-47 locale for speech recognition.
        on_device: Force on-device recognition (Darwin only).
    """
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.speech import DarwinSpeechBackend

        return DarwinSpeechBackend(locale=locale, on_device=on_device)
    elif platform == "linux":
        from sociopsi.platform.speech import LinuxSpeechBackend

        return LinuxSpeechBackend()
    else:
        raise SensorUnavailable(f"No speech backend for platform: {platform}")


def get_audio_backend() -> AudioBackend:
    """Get the TTS and sound playback backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.audio import DarwinAudioBackend

        return DarwinAudioBackend()
    elif platform == "linux":
        from sociopsi.platform.audio import LinuxAudioBackend

        return LinuxAudioBackend()
    else:
        raise SensorUnavailable(f"No audio backend for platform: {platform}")


def get_volume_backend() -> VolumeBackend:
    """Get the volume control backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.system import DarwinVolumeBackend

        return DarwinVolumeBackend()
    elif platform == "linux":
        from sociopsi.platform.system import LinuxVolumeBackend

        return LinuxVolumeBackend()
    else:
        raise SensorUnavailable(f"No volume backend for platform: {platform}")


def get_notification_backend() -> NotificationBackend:
    """Get the notification backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.system import DarwinNotificationBackend

        return DarwinNotificationBackend()
    elif platform == "linux":
        from sociopsi.platform.system import LinuxNotificationBackend

        return LinuxNotificationBackend()
    else:
        raise SensorUnavailable(f"No notification backend for platform: {platform}")


def get_clipboard_backend() -> ClipboardBackend:
    """Get the clipboard backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.clipboard import DarwinClipboardBackend

        return DarwinClipboardBackend()
    elif platform == "linux":
        from sociopsi.platform.clipboard import LinuxClipboardBackend

        return LinuxClipboardBackend()
    else:
        raise SensorUnavailable(f"No clipboard backend for platform: {platform}")


def get_screenshot_backend() -> ScreenshotBackend:
    """Get the screenshot backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.screenshot import DarwinScreenshotBackend

        return DarwinScreenshotBackend()
    elif platform == "linux":
        from sociopsi.platform.screenshot import LinuxScreenshotBackend

        return LinuxScreenshotBackend()
    else:
        raise SensorUnavailable(f"No screenshot backend for platform: {platform}")


def get_app_backend() -> AppBackend:
    """Get the app control backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.apps import DarwinAppBackend

        return DarwinAppBackend()
    elif platform == "linux":
        from sociopsi.platform.apps import LinuxAppBackend

        return LinuxAppBackend()
    else:
        raise SensorUnavailable(f"No app backend for platform: {platform}")


def get_network_backend() -> NetworkControlBackend:
    """Get the network control backend for the current platform."""
    platform = _detect_platform()
    if platform == "darwin":
        from sociopsi.platform.network import DarwinNetworkBackend

        return DarwinNetworkBackend()
    elif platform == "linux":
        from sociopsi.platform.network import LinuxNetworkBackend

        return LinuxNetworkBackend()
    else:
        raise SensorUnavailable(f"No network backend for platform: {platform}")


__all__ = [
    "AppBackend",
    "AudioBackend",
    "BatteryInfo",
    "ClipboardBackend",
    "DeviceBackend",
    "DisplayBackend",
    "DisplayInfo",
    "NetworkControlBackend",
    "NotificationBackend",
    "PowerBackend",
    "ScreenshotBackend",
    "SensorUnavailable",
    "SpeechBackend",
    "ThermalBackend",
    "ThermalInfo",
    "ThunderboltDevice",
    "USBDevice",
    "VoiceInfo",
    "VolumeBackend",
    "get_app_backend",
    "get_audio_backend",
    "get_clipboard_backend",
    "get_device_backend",
    "get_display_backend",
    "get_network_backend",
    "get_notification_backend",
    "get_power_backend",
    "get_screenshot_backend",
    "get_speech_backend",
    "get_thermal_backend",
    "get_volume_backend",
]

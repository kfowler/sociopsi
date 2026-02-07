"""Tests for platform abstraction backends."""

from unittest.mock import MagicMock, patch

import pytest

from sociopsi.platform.base import (
    AppBackend,
    ClipboardBackend,
    DeviceBackend,
    NetworkControlBackend,
    NotificationBackend,
    ScreenshotBackend,
    SensorUnavailable,
    USBDevice,
    ThunderboltDevice,
    VolumeBackend,
)

# --- Backend factory tests ---


class TestBackendFactories:
    """Test that get_*_backend() returns correct backends on Darwin."""

    def test_get_volume_backend_darwin(self):
        from sociopsi.platform import get_volume_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_volume_backend()
            assert isinstance(backend, VolumeBackend)

    def test_get_notification_backend_darwin(self):
        from sociopsi.platform import get_notification_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_notification_backend()
            assert isinstance(backend, NotificationBackend)

    def test_get_clipboard_backend_darwin(self):
        from sociopsi.platform import get_clipboard_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_clipboard_backend()
            assert isinstance(backend, ClipboardBackend)

    def test_get_screenshot_backend_darwin(self):
        from sociopsi.platform import get_screenshot_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_screenshot_backend()
            assert isinstance(backend, ScreenshotBackend)

    def test_get_app_backend_darwin(self):
        from sociopsi.platform import get_app_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_app_backend()
            assert isinstance(backend, AppBackend)

    def test_get_network_backend_darwin(self):
        from sociopsi.platform import get_network_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_network_backend()
            assert isinstance(backend, NetworkControlBackend)

    def test_get_volume_backend_linux(self):
        from sociopsi.platform import get_volume_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "linux"
            backend = get_volume_backend()
            assert isinstance(backend, VolumeBackend)

    def test_get_volume_backend_unsupported(self):
        from sociopsi.platform import get_volume_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            with pytest.raises(SensorUnavailable):
                get_volume_backend()

    def test_get_device_backend_darwin(self):
        from sociopsi.platform import get_device_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "darwin"
            backend = get_device_backend()
            assert isinstance(backend, DeviceBackend)

    def test_get_device_backend_linux(self):
        from sociopsi.platform import get_device_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "linux"
            backend = get_device_backend()
            assert isinstance(backend, DeviceBackend)

    def test_get_device_backend_unsupported(self):
        from sociopsi.platform import get_device_backend

        with patch("sociopsi.platform.sys") as mock_sys:
            mock_sys.platform = "freebsd"
            with pytest.raises(SensorUnavailable):
                get_device_backend()


# --- Darwin device backend tests ---


class TestDarwinDeviceBackend:
    def test_list_usb_success(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        usb_json = '{"SPUSBDataType": [{"_name": "USB 3.1 Bus", "_items": [{"_name": "Hub", "manufacturer": "Apple"}]}]}'
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=usb_json)
            devices = backend.list_usb()
            assert len(devices) == 1
            assert devices[0].name == "Hub"
            assert devices[0].vendor == "Apple"

    def test_list_usb_empty(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"SPUSBDataType": []}')
            devices = backend.list_usb()
            assert devices == []

    def test_list_usb_timeout(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            import subprocess

            mock_run.side_effect = subprocess.TimeoutExpired(cmd="", timeout=10)
            devices = backend.list_usb()
            assert devices == []

    def test_list_bluetooth_success(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        bt_json = '{"SPBluetoothDataType": [{"device_connected": [{"AirPods": {"device_address": "AA:BB:CC", "device_rssi": -50, "device_minorType": "Headphones"}}]}]}'
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=bt_json)
            devices = backend.list_bluetooth()
            assert len(devices) == 1
            assert devices[0].name == "AirPods"
            assert devices[0].address == "AA:BB:CC"
            assert devices[0].rssi == -50

    def test_list_thunderbolt_success(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        tb_json = '{"SPThunderboltDataType": [{"_items": [{"_name": "CalDigit", "vendor_name": "CalDigit", "device_name_key": "cd1", "link_speed": "40Gb/s"}]}]}'
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=tb_json)
            devices = backend.list_thunderbolt()
            assert len(devices) == 1
            assert devices[0].name == "CalDigit"
            assert devices[0].speed == "40Gb/s"

    def test_get_ambient_light_found(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        ioreg_output = '  "ALSSensorReading" = 150\n'
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=ioreg_output)
            result = backend.get_ambient_light()
            assert result == 150

    def test_get_ambient_light_none(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = backend.get_ambient_light()
            assert result is None

    def test_get_motion_present(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="SMCMotionSensor data")
            result = backend.get_motion()
            assert result == {"status": "present", "movement": "still"}

    def test_get_motion_unavailable(self):
        from sociopsi.platform.devices import DarwinDeviceBackend

        backend = DarwinDeviceBackend()
        with patch("sociopsi.platform.devices.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            result = backend.get_motion()
            assert result is None


# --- External sensor integration tests ---


class TestExternalSensorIntegration:
    def test_get_usb_connections_uses_backend(self):
        from sociopsi.sensors.external import get_usb_connections

        mock_backend = MagicMock()
        mock_backend.list_usb.return_value = [
            USBDevice(name="Keyboard", vendor="Apple", serial="123"),
        ]
        with patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend):
            result = get_usb_connections()
            assert len(result) == 1
            assert result[0]["name"] == "Keyboard"
            assert result[0]["vendor"] == "Apple"
            assert result[0]["serial"] == "123"

    def test_get_thunderbolt_uses_backend(self):
        from sociopsi.sensors.external import get_thunderbolt_devices

        mock_backend = MagicMock()
        mock_backend.list_thunderbolt.return_value = [
            ThunderboltDevice(name="Dock", vendor="CalDigit", device_id="cd1", speed="40Gb/s"),
        ]
        with patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend):
            result = get_thunderbolt_devices()
            assert len(result) == 1
            assert result[0]["name"] == "Dock"
            assert result[0]["speed"] == "40Gb/s"

    def test_get_ambient_light_uses_backend(self):
        from sociopsi.sensors.external import get_ambient_light

        mock_backend = MagicMock()
        mock_backend.get_ambient_light.return_value = 200
        with (
            patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend),
            patch("sociopsi.sensors.external._describe_light_level", return_value="dim"),
        ):
            result = get_ambient_light()
            assert result["raw"] == 200
            assert result["normalized"] == 20

    def test_get_ambient_light_unavailable(self):
        from sociopsi.sensors.external import get_ambient_light

        mock_backend = MagicMock()
        mock_backend.get_ambient_light.return_value = None
        with patch(
            "sociopsi.sensors.external.get_device_backend",
            return_value=mock_backend,
        ):
            result = get_ambient_light()
            assert result["description"] == "unavailable"

    def test_get_motion_uses_backend(self):
        from sociopsi.sensors.external import get_motion

        mock_backend = MagicMock()
        mock_backend.get_motion.return_value = {"status": "present", "movement": "still"}
        with patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend):
            result = get_motion()
            assert result["status"] == "present"

    def test_get_motion_unavailable(self):
        from sociopsi.sensors.external import get_motion

        mock_backend = MagicMock()
        mock_backend.get_motion.return_value = None
        with patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend):
            result = get_motion()
            assert result["status"] == "unavailable"

    def test_get_bluetooth_uses_backend(self):
        from sociopsi.sensors.external import get_bluetooth_devices
        from sociopsi.types import BluetoothDevice

        mock_backend = MagicMock()
        mock_backend.list_bluetooth.return_value = [
            BluetoothDevice(name="AirPods", address="AA:BB:CC", rssi=-50),
        ]
        with patch("sociopsi.sensors.external.get_device_backend", return_value=mock_backend):
            result = get_bluetooth_devices()
            assert len(result) == 1
            assert result[0].name == "AirPods"


# --- Darwin volume backend tests ---


class TestDarwinVolumeBackend:
    def test_set_volume_success(self):
        from sociopsi.platform.system import DarwinVolumeBackend

        backend = DarwinVolumeBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.set_volume(50)
            assert result["set_to"] == 50
            mock_run.assert_called_once()

    def test_set_volume_clamped(self):
        from sociopsi.platform.system import DarwinVolumeBackend

        backend = DarwinVolumeBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.set_volume(150)
            assert result["set_to"] == 100

    def test_get_volume_success(self):
        from sociopsi.platform.system import DarwinVolumeBackend

        backend = DarwinVolumeBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="75\n")
            result = backend.get_volume()
            assert result == 75

    def test_get_volume_failure(self):
        from sociopsi.platform.system import DarwinVolumeBackend

        backend = DarwinVolumeBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = backend.get_volume()
            assert result is None


# --- Darwin notification backend tests ---


class TestDarwinNotificationBackend:
    def test_notify_acknowledged(self):
        from sociopsi.platform.system import DarwinNotificationBackend

        backend = DarwinNotificationBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="button returned:OK")
            result = backend.notify("Test", "Hello", 5)
            assert result["sent"] is True
            assert result["acknowledged"] is True

    def test_notify_timed_out(self):
        from sociopsi.platform.system import DarwinNotificationBackend

        backend = DarwinNotificationBackend()
        with patch("sociopsi.platform.system.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="button returned:OK, gave up:true"
            )
            result = backend.notify("Test", "Hello", 5)
            assert result["sent"] is True
            assert result["acknowledged"] is False


# --- Darwin clipboard backend tests ---


class TestDarwinClipboardBackend:
    def test_read_clipboard_success(self):
        from sociopsi.platform.clipboard import DarwinClipboardBackend

        backend = DarwinClipboardBackend()
        with patch("sociopsi.platform.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hello world")
            result = backend.read_clipboard()
            assert result == "hello world"

    def test_read_clipboard_empty(self):
        from sociopsi.platform.clipboard import DarwinClipboardBackend

        backend = DarwinClipboardBackend()
        with patch("sociopsi.platform.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = backend.read_clipboard()
            assert result is None


# --- Darwin screenshot backend tests ---


class TestDarwinScreenshotBackend:
    def test_take_screenshot_success(self):
        from sociopsi.platform.screenshot import DarwinScreenshotBackend

        backend = DarwinScreenshotBackend()
        with patch("sociopsi.platform.screenshot.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert backend.take_screenshot("/tmp/test.png") is True

    def test_take_screenshot_failure(self):
        from sociopsi.platform.screenshot import DarwinScreenshotBackend

        backend = DarwinScreenshotBackend()
        with patch("sociopsi.platform.screenshot.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert backend.take_screenshot("/tmp/test.png") is False


# --- Darwin app backend tests ---


class TestDarwinAppBackend:
    def test_open_app_success(self):
        from sociopsi.platform.apps import DarwinAppBackend

        backend = DarwinAppBackend()
        with patch("sociopsi.platform.apps.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.open_app("Safari")
            assert result["opened"] is True
            assert result["app"] == "Safari"

    def test_close_app_success(self):
        from sociopsi.platform.apps import DarwinAppBackend

        backend = DarwinAppBackend()
        with patch("sociopsi.platform.apps.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.close_app("Safari")
            assert result["closed"] is True


# --- Darwin network backend tests ---


class TestDarwinNetworkBackend:
    def test_connect_wifi_found(self):
        from sociopsi.platform.network import DarwinNetworkBackend

        backend = DarwinNetworkBackend()
        mock_output = "Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: aa:bb:cc:dd:ee:ff\n"
        with patch("sociopsi.platform.network.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            result = backend.connect_wifi()
            assert result["connected"] is True
            assert result["device"] == "en0"

    def test_connect_wifi_not_found(self):
        from sociopsi.platform.network import DarwinNetworkBackend

        backend = DarwinNetworkBackend()
        with patch("sociopsi.platform.network.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Hardware Port: Ethernet\nDevice: en1\n"
            )
            result = backend.connect_wifi()
            assert "error" in result

    def test_list_interfaces(self):
        from sociopsi.platform.network import DarwinNetworkBackend

        backend = DarwinNetworkBackend()
        mock_output = "Hardware Port: Wi-Fi\nDevice: en0\n\nHardware Port: Ethernet\nDevice: en1\n"
        with patch("sociopsi.platform.network.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            result = backend.list_interfaces()
            assert len(result) == 2
            assert result[0]["name"] == "Wi-Fi"
            assert result[0]["device"] == "en0"


# --- Linux clipboard backend tests ---


class TestLinuxClipboardBackend:
    def test_read_clipboard_wl_paste(self):
        from sociopsi.platform.clipboard import LinuxClipboardBackend

        backend = LinuxClipboardBackend()
        with patch("sociopsi.platform.clipboard.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="wayland text")
            result = backend.read_clipboard()
            assert result == "wayland text"

    def test_read_clipboard_xclip_fallback(self):
        from sociopsi.platform.clipboard import LinuxClipboardBackend

        backend = LinuxClipboardBackend()
        with patch("sociopsi.platform.clipboard.subprocess.run") as mock_run:
            # wl-paste fails, xclip succeeds
            mock_run.side_effect = [
                FileNotFoundError(),
                MagicMock(returncode=0, stdout="x11 text"),
            ]
            result = backend.read_clipboard()
            assert result == "x11 text"

    def test_read_clipboard_all_fail(self):
        from sociopsi.platform.clipboard import LinuxClipboardBackend

        backend = LinuxClipboardBackend()
        with patch("sociopsi.platform.clipboard.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = backend.read_clipboard()
            assert result is None


# --- Linux screenshot backend tests ---


class TestLinuxScreenshotBackend:
    def test_take_screenshot_scrot(self):
        from sociopsi.platform.screenshot import LinuxScreenshotBackend

        backend = LinuxScreenshotBackend()
        with patch("sociopsi.platform.screenshot.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/scrot"
            with patch("sociopsi.platform.screenshot.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                assert backend.take_screenshot("/tmp/test.png") is True

    def test_take_screenshot_no_tools(self):
        from sociopsi.platform.screenshot import LinuxScreenshotBackend

        backend = LinuxScreenshotBackend()
        with patch("sociopsi.platform.screenshot.shutil.which", return_value=None):
            assert backend.take_screenshot("/tmp/test.png") is False


# --- Action-level integration tests ---


class TestActionIntegration:
    def test_set_volume_uses_backend(self):
        from sociopsi.actions.system import set_volume

        mock_backend = MagicMock()
        mock_backend.set_volume.return_value = {"set_to": 50}
        with (
            patch("sociopsi.actions.system.get_volume_backend", return_value=mock_backend),
            patch("sociopsi.actions.system._describe_volume", return_value="moderate volume"),
        ):
            result = set_volume(50)
            assert result["set_to"] == 50
            assert "description" in result

    def test_open_app_uses_backend(self):
        from sociopsi.actions.environment import open_app

        mock_backend = MagicMock()
        mock_backend.open_app.return_value = {"opened": True, "app": "Firefox"}
        with patch("sociopsi.actions.environment.get_app_backend", return_value=mock_backend):
            result = open_app("Firefox")
            assert result["opened"] is True
            assert "description" in result

    def test_read_clipboard_uses_backend(self):
        from sociopsi.actions.awareness import read_clipboard

        mock_backend = MagicMock()
        mock_backend.read_clipboard.return_value = "https://example.com"
        with patch("sociopsi.actions.awareness.get_clipboard_backend", return_value=mock_backend):
            result = read_clipboard()
            assert result["type"] == "url"
            assert result["length"] == 19

    def test_connect_network_uses_backend(self):
        from sociopsi.actions.environment import connect_network

        mock_backend = MagicMock()
        mock_backend.connect_wifi.return_value = {"connected": True, "device": "wlan0"}
        with patch("sociopsi.actions.environment.get_network_backend", return_value=mock_backend):
            result = connect_network()
            assert result["connected"] is True
            assert "description" in result

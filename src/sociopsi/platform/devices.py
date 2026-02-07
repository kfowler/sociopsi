"""Device enumeration backends for Darwin and Linux."""

import json
import logging
import subprocess

from sociopsi.platform.base import DeviceBackend, ThunderboltDevice, USBDevice
from sociopsi.types import BluetoothDevice

logger = logging.getLogger(__name__)


class DarwinDeviceBackend(DeviceBackend):
    """macOS device enumeration via system_profiler and ioreg."""

    def list_usb(self) -> list[USBDevice]:
        devices: list[USBDevice] = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)

            def extract(items: list[dict]) -> None:
                for item in items:
                    if "_name" in item and item.get("_name") != "USB 3.1 Bus":
                        devices.append(
                            USBDevice(
                                name=item.get("_name", "Unknown"),
                                vendor=item.get("manufacturer", "Unknown"),
                                serial=item.get("serial_num", None),
                            )
                        )
                    if "_items" in item:
                        extract(item["_items"])

            extract(data.get("SPUSBDataType", []))
        except subprocess.TimeoutExpired:
            logger.warning("USB scan timed out")
        except (ValueError, KeyError) as e:
            logger.warning(f"USB data parse error: {e}")
        except FileNotFoundError:
            logger.warning("system_profiler not found")
        return devices

    def list_bluetooth(self) -> list[BluetoothDevice]:
        devices: list[BluetoothDevice] = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPBluetoothDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)
            bt_data = data.get("SPBluetoothDataType", [{}])[0]
            connected = bt_data.get("device_connected", [])

            for device_dict in connected:
                for name, info in device_dict.items():
                    devices.append(
                        BluetoothDevice(
                            name=name,
                            address=info.get("device_address", "unknown"),
                            rssi=info.get("device_rssi", 0),
                            device_type=info.get("device_minorType", None),
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Bluetooth scan timed out")
        except (ValueError, KeyError) as e:
            logger.warning(f"Bluetooth data parse error: {e}")
        except FileNotFoundError:
            logger.warning("system_profiler not found")
        return devices

    def list_thunderbolt(self) -> list[ThunderboltDevice]:
        devices: list[ThunderboltDevice] = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPThunderboltDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)
            tb_data = data.get("SPThunderboltDataType", [])

            for bus in tb_data:
                for device in bus.get("_items", []):
                    devices.append(
                        ThunderboltDevice(
                            name=device.get("_name", "Unknown"),
                            vendor=device.get("vendor_name", "Unknown"),
                            device_id=device.get("device_name_key", None),
                            speed=device.get("link_speed", "Unknown"),
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Thunderbolt scan timed out")
        except (ValueError, KeyError) as e:
            logger.warning(f"Thunderbolt data parse error: {e}")
        except FileNotFoundError:
            logger.warning("system_profiler not found")
        return devices

    def get_ambient_light(self) -> int | None:
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-c", "AppleLMUController"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            for line in result.stdout.split("\n"):
                if "ALSSensorReading" in line:
                    return int(line.split("=")[-1].strip())
        except subprocess.TimeoutExpired:
            logger.warning("Ambient light sensor timed out")
        except ValueError, FileNotFoundError:
            pass
        return None

    def get_motion(self) -> dict[str, str] | None:
        try:
            result = subprocess.run(
                ["ioreg", "-r", "-c", "SMCMotionSensor"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.stdout.strip():
                return {"status": "present", "movement": "still"}
        except subprocess.TimeoutExpired:
            logger.warning("Motion sensor timed out")
        except FileNotFoundError:
            pass
        return None


class LinuxDeviceBackend(DeviceBackend):
    """Linux device enumeration via lsusb, bluetoothctl, lspci, sysfs."""

    def list_usb(self) -> list[USBDevice]:
        devices: list[USBDevice] = []
        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # lsusb format: "Bus 001 Device 002: ID 1234:5678 Vendor Product"
                parts = line.split("ID ", 1)
                if len(parts) == 2:
                    id_and_name = parts[1]
                    name_parts = id_and_name.split(" ", 1)
                    name = name_parts[1] if len(name_parts) > 1 else "Unknown"
                    devices.append(
                        USBDevice(
                            name=name,
                            vendor=name.split(" ")[0] if name != "Unknown" else "Unknown",
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("USB scan timed out")
        except FileNotFoundError:
            logger.warning("lsusb not found")
        return devices

    def list_bluetooth(self) -> list[BluetoothDevice]:
        devices: list[BluetoothDevice] = []
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # Format: "Device AA:BB:CC:DD:EE:FF DeviceName"
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    devices.append(
                        BluetoothDevice(
                            name=parts[2],
                            address=parts[1],
                            rssi=0,
                        )
                    )
        except subprocess.TimeoutExpired:
            logger.warning("Bluetooth scan timed out")
        except FileNotFoundError:
            # Try hcitool as fallback
            try:
                result = subprocess.run(
                    ["hcitool", "con"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for line in result.stdout.strip().split("\n"):
                    if "ACL" in line or "SCO" in line:
                        parts = line.strip().split()
                        for i, part in enumerate(parts):
                            if ":" in part and len(part) == 17:  # MAC address
                                devices.append(
                                    BluetoothDevice(
                                        name=parts[i + 1] if i + 1 < len(parts) else "Unknown",
                                        address=part,
                                        rssi=0,
                                    )
                                )
                                break
            except subprocess.TimeoutExpired, FileNotFoundError:
                logger.warning("No Bluetooth tools available")
        return devices

    def list_thunderbolt(self) -> list[ThunderboltDevice]:
        devices: list[ThunderboltDevice] = []
        try:
            # Use boltctl for Thunderbolt on Linux
            result = subprocess.run(
                ["boltctl", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            current_name = None
            current_vendor = None
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Name:"):
                    current_name = line.split(":", 1)[1].strip()
                elif line.startswith("Vendor:"):
                    current_vendor = line.split(":", 1)[1].strip()
                elif line == "" and current_name:
                    devices.append(
                        ThunderboltDevice(
                            name=current_name,
                            vendor=current_vendor or "Unknown",
                        )
                    )
                    current_name = None
                    current_vendor = None
            # Catch last device
            if current_name:
                devices.append(
                    ThunderboltDevice(
                        name=current_name,
                        vendor=current_vendor or "Unknown",
                    )
                )
        except subprocess.TimeoutExpired:
            logger.warning("Thunderbolt scan timed out")
        except FileNotFoundError:
            # Fallback: check sysfs
            try:
                from pathlib import Path

                tb_base = Path("/sys/bus/thunderbolt/devices")
                if tb_base.exists():
                    for dev_dir in tb_base.iterdir():
                        name_file = dev_dir / "device_name"
                        vendor_file = dev_dir / "vendor_name"
                        if name_file.exists():
                            devices.append(
                                ThunderboltDevice(
                                    name=name_file.read_text().strip(),
                                    vendor=vendor_file.read_text().strip()
                                    if vendor_file.exists()
                                    else "Unknown",
                                )
                            )
            except OSError:
                logger.warning("No Thunderbolt sysfs access")
        return devices

    def get_ambient_light(self) -> int | None:
        try:
            from pathlib import Path

            iio_base = Path("/sys/bus/iio/devices")
            if not iio_base.exists():
                return None
            for dev_dir in iio_base.iterdir():
                name_file = dev_dir / "name"
                if name_file.exists():
                    name = name_file.read_text().strip().lower()
                    if "light" in name or "als" in name:
                        # Try in_illuminance_raw first, then in_intensity_both_raw
                        for attr in ("in_illuminance_raw", "in_intensity_both_raw"):
                            raw_file = dev_dir / attr
                            if raw_file.exists():
                                return int(raw_file.read_text().strip())
        except ValueError, OSError:
            pass
        return None

    def get_motion(self) -> dict[str, str] | None:
        try:
            from pathlib import Path

            iio_base = Path("/sys/bus/iio/devices")
            if not iio_base.exists():
                return None
            for dev_dir in iio_base.iterdir():
                name_file = dev_dir / "name"
                if name_file.exists():
                    name = name_file.read_text().strip().lower()
                    if "accel" in name:
                        return {"status": "present", "movement": "still"}
        except OSError:
            pass
        return None

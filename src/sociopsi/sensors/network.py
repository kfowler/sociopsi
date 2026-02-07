"""Network sensing: ARP scan, ping, port scan, etc."""

import re
import subprocess
from typing import Any

from sociopsi.types import NetworkDevice


def scan_local_network(depth: str = "quick") -> list[NetworkDevice]:
    """Scan local network for devices."""
    devices: list[NetworkDevice] = []

    try:
        # Get local network range
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Find the active network interface IP
        local_ip = None
        for line in result.stdout.split("\n"):
            if "inet " in line and "127.0.0.1" not in line:
                match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                if match:
                    local_ip = match.group(1)
                    break

        if not local_ip:
            return devices

        # Derive network range (assume /24)
        network = ".".join(local_ip.split(".")[:3]) + ".0/24"

        if depth == "quick":
            # Use ARP table for quick scan
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            for line in result.stdout.split("\n"):
                # Parse: hostname (ip) at mac on interface
                match = re.search(
                    r"(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)",
                    line,
                    re.IGNORECASE,
                )
                if match:
                    hostname, ip, mac = match.groups()
                    devices.append(
                        NetworkDevice(
                            ip=ip,
                            mac=mac if mac != "(incomplete)" else None,
                            hostname=hostname if hostname != "?" else None,
                        )
                    )

        else:
            # Thorough scan with nmap if available
            result = subprocess.run(
                ["nmap", "-sn", network],
                capture_output=True,
                text=True,
                timeout=60,
            )

            current_device: dict[str, Any] = {}
            for line in result.stdout.split("\n"):
                if "Nmap scan report for" in line:
                    if current_device:
                        devices.append(
                            NetworkDevice(
                                ip=current_device.get("ip", ""),
                                hostname=current_device.get("hostname"),
                                mac=current_device.get("mac"),
                                vendor=current_device.get("vendor"),
                            )
                        )
                    current_device = {}
                    # Parse: Nmap scan report for hostname (ip) or just ip
                    match = re.search(r"for (\S+)(?: \((\d+\.\d+\.\d+\.\d+)\))?", line)
                    if match:
                        if match.group(2):
                            current_device["hostname"] = match.group(1)
                            current_device["ip"] = match.group(2)
                        else:
                            current_device["ip"] = match.group(1)

                elif "MAC Address:" in line:
                    match = re.search(r"MAC Address: ([0-9A-F:]+)(?: \((.+)\))?", line)
                    if match:
                        current_device["mac"] = match.group(1)
                        if match.group(2):
                            current_device["vendor"] = match.group(2)

            if current_device:
                devices.append(
                    NetworkDevice(
                        ip=current_device.get("ip", ""),
                        hostname=current_device.get("hostname"),
                        mac=current_device.get("mac"),
                        vendor=current_device.get("vendor"),
                    )
                )

    except subprocess.TimeoutExpired, FileNotFoundError:
        pass

    return devices


def ping_host(host: str, count: int = 3) -> dict[str, Any]:
    """Ping a host to check if it's alive."""
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "1000", host],
            capture_output=True,
            text=True,
            timeout=count + 5,
        )

        if result.returncode == 0:
            # Parse statistics
            stats: dict[str, Any] = {"alive": True, "host": host}

            # Extract round-trip times
            for line in result.stdout.split("\n"):
                if "round-trip" in line or "rtt" in line:
                    # Parse: round-trip min/avg/max/stddev = 1.234/2.345/3.456/0.567 ms
                    match = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", line)
                    if match:
                        stats["min_ms"] = float(match.group(1))
                        stats["avg_ms"] = float(match.group(2))
                        stats["max_ms"] = float(match.group(3))
                        stats["description"] = _describe_latency(float(match.group(2)))

            return stats
        else:
            from sociopsi.describe import describe_ping_failure

            return {
                "alive": False,
                "host": host,
                "description": describe_ping_failure("unreachable"),
            }

    except subprocess.TimeoutExpired:
        from sociopsi.describe import describe_ping_failure

        return {"alive": False, "host": host, "description": describe_ping_failure("timeout")}
    except FileNotFoundError:
        return {"alive": False, "host": host, "error": "ping not available"}


def _describe_latency(ms: float) -> str:
    """Describe latency experientially."""
    from sociopsi.describe import describe_latency

    return describe_latency(ms)


def probe_host(host: str, ports: list[int] | None = None) -> dict[str, Any]:
    """Probe a host's ports."""
    if ports is None:
        ports = [22, 80, 443, 8080, 5000]  # Common ports

    results: dict[str, Any] = {"host": host, "ports": {}}

    try:
        port_spec = ",".join(str(p) for p in ports)
        result = subprocess.run(
            ["nmap", "-Pn", "-p", port_spec, host],
            capture_output=True,
            text=True,
            timeout=30,
        )

        open_ports: list[int] = []
        for line in result.stdout.split("\n"):
            # Parse: 22/tcp open ssh
            match = re.search(r"(\d+)/\w+\s+(open|closed|filtered)\s+(\S+)?", line)
            if match:
                port = int(match.group(1))
                state = match.group(2)
                service = match.group(3) or "unknown"
                results["ports"][port] = {"state": state, "service": service}
                if state == "open":
                    open_ports.append(port)

        results["open_count"] = len(open_ports)
        results["description"] = _describe_host(open_ports)

    except subprocess.TimeoutExpired:
        results["error"] = "timeout"
        results["description"] = "probe timed out"
    except FileNotFoundError:
        # Fallback to basic socket check
        import socket

        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result_code = sock.connect_ex((host, port))
                sock.close()
                results["ports"][port] = {
                    "state": "open" if result_code == 0 else "closed",
                    "service": "unknown",
                }
            except OSError:
                results["ports"][port] = {"state": "error", "service": "unknown"}

    return results


def _describe_host(open_ports: list[int]) -> str:
    """Describe a host based on its open ports."""
    if not open_ports:
        return "closed, guarded, silent"

    descriptions = []
    if 22 in open_ports:
        descriptions.append("accepting connections (SSH)")
    if 80 in open_ports or 443 in open_ports:
        descriptions.append("serving the web")
    if 5000 in open_ports or 8080 in open_ports:
        descriptions.append("running services")

    return ", ".join(descriptions) if descriptions else f"{len(open_ports)} ports open"


def trace_route(host: str, max_hops: int = 15) -> dict[str, Any]:
    """Trace route to a host."""
    hops: list[dict[str, Any]] = []

    try:
        result = subprocess.run(
            ["traceroute", "-m", str(max_hops), "-w", "2", host],
            capture_output=True,
            text=True,
            timeout=max_hops * 3,
        )

        for line in result.stdout.split("\n"):
            # Parse: 1  router (192.168.1.1)  1.234 ms  2.345 ms  3.456 ms
            match = re.search(r"^\s*(\d+)\s+(\S+)", line)
            if match:
                hop_num = int(match.group(1))
                hop_host = match.group(2)

                # Extract IP if present
                ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
                ip = ip_match.group(1) if ip_match else None

                # Extract times
                times = re.findall(r"([\d.]+)\s*ms", line)
                avg_time = sum(float(t) for t in times) / len(times) if times else None

                if hop_host != "*":
                    hops.append(
                        {
                            "hop": hop_num,
                            "host": hop_host,
                            "ip": ip,
                            "avg_ms": avg_time,
                        }
                    )
                else:
                    hops.append({"hop": hop_num, "host": "*", "description": "silence"})

        return {
            "destination": host,
            "hops": hops,
            "total_hops": len(hops),
            "description": _describe_route(hops),
        }

    except subprocess.TimeoutExpired:
        return {"destination": host, "error": "timeout", "description": "path lost"}
    except FileNotFoundError:
        return {"destination": host, "error": "traceroute not available"}


def _describe_route(hops: list[dict[str, Any]]) -> str:
    """Describe the route experientially."""
    from sociopsi.describe import describe_state

    if not hops:
        return describe_state("network route", "no path found", "tracing path to destination")
    silent_count = sum(1 for h in hops if h.get("host") == "*")
    return describe_state(
        "network route", f"{len(hops)} hops, {silent_count} silent", "tracing path to destination"
    )

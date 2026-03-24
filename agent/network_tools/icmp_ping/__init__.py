"""ICMP Ping 探测核心 — 通过系统 ping 命令实现。

当前实现使用 subprocess 调用系统 ping。
probes/icmp_probe.py 作为适配层调用本模块。
"""
import platform
import subprocess
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ICMPPingResult:
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    error: Optional[str] = None


def ping(target: str, count: int = 1, timeout: int = 10) -> ICMPPingResult:
    """Execute ICMP ping and return parsed result."""
    try:
        is_windows = platform.system() == 'Windows'
        if is_windows:
            cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), target]
        else:
            cmd = ['ping', '-c', str(count), '-W', str(timeout), target]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        output = result.stdout

        if result.returncode != 0:
            return ICMPPingResult(success=False, packet_loss=100.0,
                                 error=f'ping failed: {result.stderr.strip()}')

        latency = _parse_avg_latency(output)
        packet_loss = _parse_packet_loss(output)

        return ICMPPingResult(
            success=True,
            latency=latency,
            packet_loss=packet_loss,
        )
    except subprocess.TimeoutExpired:
        return ICMPPingResult(success=False, error='Request timed out')
    except Exception as e:
        return ICMPPingResult(success=False, error=str(e))


def _parse_avg_latency(output: str) -> Optional[float]:
    # Linux: rtt min/avg/max/mdev = 0.030/0.045/0.060/0.015 ms
    m = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms', output)
    if m:
        return float(m.group(1))
    # Windows: Average = 12ms
    m = re.search(r'Average = (\d+)ms', output)
    if m:
        return float(m.group(1))
    # Alternative: time=12.5 ms
    times = re.findall(r'time[=<](\d+\.?\d*)\s*ms', output)
    if times:
        return sum(float(t) for t in times) / len(times)
    return None


def _parse_packet_loss(output: str) -> float:
    m = re.search(r'(\d+)% packet loss', output)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+)% loss', output)
    if m:
        return float(m.group(1))
    return 0.0

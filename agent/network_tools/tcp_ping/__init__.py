"""TCP Ping 探测核心 — 基于 Network-Monitoring-Tools/tcp_ping 实现。

参考上游: Network-Monitoring-Tools/tcp_ping/monitor_tcp_ping.py
上游函数: tcp_connect_single(target_ip, target_port, timeout)
probes/tcp_probe.py 作为适配层调用本模块。
"""
import socket
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class TCPPingResult:
    success: bool = False
    latency: Optional[float] = None
    error: Optional[str] = None


def ping(target: str, port: int = 80, timeout: int = 10) -> TCPPingResult:
    """Execute TCP connect probe and return parsed result.

    Aligned with upstream tcp_connect_single(target_ip, target_port, timeout).
    """
    try:
        start = time.time()
        sock = socket.create_connection((target, port), timeout=timeout)
        elapsed = (time.time() - start) * 1000
        sock.close()
        return TCPPingResult(success=True, latency=round(elapsed, 2))
    except socket.timeout:
        return TCPPingResult(success=False, error='Connection timed out')
    except ConnectionRefusedError:
        return TCPPingResult(success=False, error=f'Connection refused on port {port}')
    except Exception as e:
        return TCPPingResult(success=False, error=str(e))

"""TCP Ping 探测核心 — 薄包装层，转发到 vendor/Network-Monitoring-Tools/tcp_ping。

真实实现来源: agent/vendor/Network-Monitoring-Tools/tcp_ping/monitor_tcp_ping.py
上游函数: tcp_connect_single(target_ip, target_port, timeout)
probes/tcp_probe.py 作为适配层调用本模块。
"""
import importlib.util
import os
from dataclasses import dataclass
from typing import Optional

# --- 通过 importlib 加载 vendor 模块 ---
_VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'vendor',
    'Network-Monitoring-Tools', 'tcp_ping', 'monitor_tcp_ping.py',
)
_spec = importlib.util.spec_from_file_location('vendor_tcp_ping', os.path.normpath(_VENDOR_DIR))
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)

# 上游真实函数引用
_vendor_tcp_connect_single = _vendor.tcp_connect_single


@dataclass
class TCPPingResult:
    success: bool = False
    latency: Optional[float] = None
    error: Optional[str] = None


def ping(target: str, port: int = 80, timeout: int = 10) -> TCPPingResult:
    """Execute TCP connect probe via vendor tcp_connect_single."""
    try:
        success, rtt_ms, error_msg = _vendor_tcp_connect_single(target, port, timeout)
        return TCPPingResult(
            success=success,
            latency=round(rtt_ms, 2) if rtt_ms is not None else None,
            error=error_msg,
        )
    except Exception as e:
        return TCPPingResult(success=False, error=str(e))


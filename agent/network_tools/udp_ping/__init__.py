"""UDP Ping 探测核心 — 薄包装层，转发到 vendor/Network-Monitoring-Tools/udp_ping。

真实实现来源: agent/vendor/Network-Monitoring-Tools/udp_ping/ping_udp.py
上游函数: _perform_ping_batch()
probes/udp_probe.py 作为适配层调用本模块。
"""
import importlib.util
import os
import socket
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# --- 通过 importlib 加载 vendor 模块 ---
_VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'vendor',
    'Network-Monitoring-Tools', 'udp_ping', 'ping_udp.py',
)
_spec = importlib.util.spec_from_file_location('vendor_udp_ping', os.path.normpath(_VENDOR_DIR))
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)

# 上游真实函数引用
_vendor_perform_ping_batch = _vendor._perform_ping_batch


@dataclass
class UDPPingResult:
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    jitter: Optional[float] = None
    rtts: list[float] = field(default_factory=list)
    error: Optional[str] = None


def ping(target: str, port: int = 53, count: int = 5,
         timeout: int = 10, interval: float = 0.2) -> UDPPingResult:
    """Send UDP packets via vendor _perform_ping_batch and return results."""
    try:
        # 解析目标地址（vendor 需要 (ip, port) 元组）
        addr_info = socket.getaddrinfo(target, port, socket.AF_INET, socket.SOCK_DGRAM)
        if not addr_info:
            return UDPPingResult(success=False, error=f'Cannot resolve {target}')
        target_addr = addr_info[0][4]  # (ip, port) tuple
    except socket.gaierror as e:
        return UDPPingResult(success=False, error=f'DNS resolution failed: {e}')

    try:
        results, loss_percent, rtt_min, rtt_avg, rtt_max, rtt_stdev, jitter, duration = \
            _vendor_perform_ping_batch(
                target_addr=target_addr,
                batch_count=count,
                interval=interval,
                timeout=min(timeout / max(count, 1), 2.0),
                payload_size=64,
                buffer_size=1024,
                verbose=False,
            )
    except Exception as e:
        return UDPPingResult(success=False, error=str(e))

    sent = results.get('sent', 0) if isinstance(results, dict) else 0
    received = results.get('received', 0) if isinstance(results, dict) else 0
    rtts = results.get('rtts', []) if isinstance(results, dict) else []

    if sent == 0:
        return UDPPingResult(success=False, error='No packets sent')

    if received == 0:
        return UDPPingResult(success=False, packet_loss=100.0, error='All packets lost')

    latency_val = round(rtt_avg, 2) if not math.isnan(rtt_avg) else None
    jitter_val = round(jitter, 2) if not math.isnan(jitter) else None
    loss_val = round(loss_percent, 2)

    return UDPPingResult(
        success=True,
        latency=latency_val,
        packet_loss=loss_val,
        jitter=jitter_val,
        rtts=rtts,
    )


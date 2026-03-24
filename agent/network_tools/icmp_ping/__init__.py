"""ICMP Ping 探测核心 — 薄包装层，转发到 vendor/Network-Monitoring-Tools/icmp_ping。

真实实现来源: agent/vendor/Network-Monitoring-Tools/icmp_ping/monitor_ping.py
上游函数: run_ping(), parse_ping_output()
probes/icmp_probe.py 作为适配层调用本模块。
"""
import importlib.util
import os
from dataclasses import dataclass
from typing import Optional

# --- 通过 importlib 加载 vendor 模块（目录名含连字符，无法直接 import）---
_VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'vendor',
    'Network-Monitoring-Tools', 'icmp_ping', 'monitor_ping.py',
)
_spec = importlib.util.spec_from_file_location('vendor_icmp_ping', os.path.normpath(_VENDOR_DIR))
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)

# 上游真实函数引用
_vendor_run_ping = _vendor.run_ping
_vendor_parse_ping_output = _vendor.parse_ping_output


@dataclass
class ICMPPingResult:
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    error: Optional[str] = None


def ping(target: str, count: int = 1, timeout: int = 10) -> ICMPPingResult:
    """Execute ICMP ping via vendor run_ping + parse_ping_output."""
    try:
        output, is_error = _vendor_run_ping(target, count, timeout)

        if is_error and not output:
            return ICMPPingResult(success=False, packet_loss=100.0,
                                 error='ping command execution failed')

        tx, rx, loss_str, rtt_min, rtt_avg, rtt_max, rtt_mdev, parse_error = \
            _vendor_parse_ping_output(output, count)

        if parse_error:
            return ICMPPingResult(success=False, error='Failed to parse ping output')

        # 解析丢包率
        try:
            packet_loss = float(loss_str) if loss_str not in ('ERR', 'N/A') else 100.0
        except (ValueError, TypeError):
            packet_loss = 100.0

        # 解析平均延迟
        latency = None
        try:
            if rtt_avg not in ('N/A', 'ERR'):
                latency = float(rtt_avg)
        except (ValueError, TypeError):
            pass

        success = packet_loss < 100.0
        return ICMPPingResult(
            success=success,
            latency=latency,
            packet_loss=packet_loss,
        )
    except Exception as e:
        return ICMPPingResult(success=False, error=str(e))


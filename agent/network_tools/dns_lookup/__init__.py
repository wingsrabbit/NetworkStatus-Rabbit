"""DNS 查询探测核心 — 薄包装层，转发到 vendor/Network-Monitoring-Tools/dns_lookup。

真实实现来源: agent/vendor/Network-Monitoring-Tools/dns_lookup/monitor_dns.py
上游函数: resolve_dns_with_server()
probes/dns_probe.py 作为适配层调用本模块。
"""
import importlib.util
import os
from dataclasses import dataclass
from typing import Optional

# --- 通过 importlib 加载 vendor 模块 ---
_VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'vendor',
    'Network-Monitoring-Tools', 'dns_lookup', 'monitor_dns.py',
)
_spec = importlib.util.spec_from_file_location('vendor_dns_lookup', os.path.normpath(_VENDOR_DIR))
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)

# 上游真实函数引用
_vendor_resolve_dns = _vendor.resolve_dns_with_server


@dataclass
class DNSProbeResult:
    success: bool = False
    latency: Optional[float] = None
    resolved_ip: Optional[str] = None
    error: Optional[str] = None


def probe(target: str, port: int = None, timeout: int = 10) -> DNSProbeResult:
    """Execute DNS lookup via vendor resolve_dns_with_server."""
    try:
        # vendor 函数签名: resolve_dns_with_server(domain, dns_server=None, use_tcp=False)
        # port 参数在 vendor 中没有直接对应，DNS 默认 53
        dns_time_str, resolved_ip, status, all_ips = _vendor_resolve_dns(target)
    except Exception as e:
        return DNSProbeResult(success=False, error=str(e))

    # 解析延迟值
    latency = None
    try:
        if dns_time_str not in ('N/A', 'ERR'):
            latency = round(float(dns_time_str), 2)
    except (ValueError, TypeError):
        pass

    success = status == 'SUCCESS'
    error_msg = None if success else status

    return DNSProbeResult(
        success=success,
        latency=latency,
        resolved_ip=resolved_ip if resolved_ip != 'N/A' else None,
        error=error_msg,
    )


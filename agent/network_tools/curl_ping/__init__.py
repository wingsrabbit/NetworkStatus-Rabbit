"""HTTP/HTTPS 探测核心 — 薄包装层，转发到 vendor/Network-Monitoring-Tools/curl_ping。

真实实现来源: agent/vendor/Network-Monitoring-Tools/curl_ping/monitor_curl.py
上游函数: run_curl(), normalize_url()
probes/http_probe.py 作为适配层调用本模块。
"""
import importlib.util
import os
import shutil
import time
from dataclasses import dataclass
from typing import Optional

# --- 通过 importlib 加载 vendor 模块 ---
_VENDOR_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', 'vendor',
    'Network-Monitoring-Tools', 'curl_ping', 'monitor_curl.py',
)
_spec = importlib.util.spec_from_file_location('vendor_curl_ping', os.path.normpath(_VENDOR_DIR))
_vendor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vendor)

# 上游真实函数引用
_vendor_run_curl = _vendor.run_curl
_vendor_normalize_url = _vendor.normalize_url


@dataclass
class HTTPProbeResult:
    success: bool = False
    status_code: Optional[int] = None
    dns_time: Optional[float] = None
    tcp_time: Optional[float] = None
    tls_time: Optional[float] = None
    ttfb: Optional[float] = None
    total_time: Optional[float] = None
    resolved_ip: Optional[str] = None
    error: Optional[str] = None


def normalize_url(target: str, port: int = None) -> str:
    """Normalize target to full URL — delegates to vendor normalize_url with port handling."""
    url = target
    if not url.startswith(('http://', 'https://')):
        scheme = 'https' if port == 443 else 'http'
        url = f'{scheme}://{target}'
        if port and port not in (80, 443):
            url = f'{scheme}://{target}:{port}'
    return url


def probe(target: str, port: int = None, timeout: int = 10) -> HTTPProbeResult:
    """Execute HTTP probe via vendor run_curl."""
    url = normalize_url(target, port)

    if not shutil.which('curl'):
        return _probe_requests_fallback(url, timeout)

    try:
        result = _vendor_run_curl(url)
    except Exception as e:
        return HTTPProbeResult(success=False, error=str(e))

    if not result.get('success', False):
        return HTTPProbeResult(success=False, error=result.get('error', 'curl failed'))

    try:
        status_code = int(result.get('http_code', 0))
    except (ValueError, TypeError):
        status_code = 0

    dns_time = result.get('dns_time')
    connect_time = result.get('connect_time')
    transfer_time = result.get('transfer_time')
    total_time = result.get('total_time')

    # vendor 返回的字段名与本项目字段映射
    tcp_time = None
    if connect_time is not None and dns_time is not None:
        tcp_time = round(connect_time - dns_time, 2) if connect_time > dns_time else round(connect_time, 2)

    return HTTPProbeResult(
        success=200 <= status_code < 400,
        status_code=status_code,
        dns_time=round(dns_time, 2) if dns_time is not None else None,
        tcp_time=tcp_time,
        tls_time=None,  # vendor run_curl 不返回 tls 拆分
        ttfb=round(transfer_time, 2) if transfer_time is not None else None,
        total_time=round(total_time, 2) if total_time is not None else None,
        resolved_ip=None,
    )


def _probe_requests_fallback(url: str, timeout: int) -> HTTPProbeResult:
    """Fallback: use Python requests module when curl is unavailable."""
    try:
        import requests
        start = time.time()
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        total = (time.time() - start) * 1000
        return HTTPProbeResult(
            success=200 <= resp.status_code < 400,
            status_code=resp.status_code,
            total_time=round(total, 2),
        )
    except Exception as e:
        return HTTPProbeResult(success=False, error=str(e))


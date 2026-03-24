"""HTTP/HTTPS 探测核心 — 基于 Network-Monitoring-Tools/curl_ping 实现。

参考上游: Network-Monitoring-Tools/curl_ping/monitor_curl.py
上游函数: normalize_url(), run_curl()
probes/http_probe.py 作为适配层调用本模块。
"""
import subprocess
import shutil
import json
import time
from dataclasses import dataclass
from typing import Optional


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
    """Normalize target to full URL.

    Aligned with upstream normalize_url(target).
    """
    url = target
    if not url.startswith(('http://', 'https://')):
        scheme = 'https' if port == 443 else 'http'
        url = f'{scheme}://{target}'
        if port and port not in (80, 443):
            url = f'{scheme}://{target}:{port}'
    return url


def probe(target: str, port: int = None, timeout: int = 10) -> HTTPProbeResult:
    """Execute HTTP probe.

    Aligned with upstream run_curl(url).
    Uses curl with detailed timing metrics; falls back to Python requests.
    """
    url = normalize_url(target, port)

    if shutil.which('curl'):
        return _probe_curl(url, timeout)
    else:
        return _probe_requests(url, timeout)


def _probe_curl(url: str, timeout: int) -> HTTPProbeResult:
    """Use curl with timing info, aligned with upstream run_curl()."""
    try:
        fmt = json.dumps({
            'dns': '%{time_namelookup}',
            'tcp': '%{time_connect}',
            'tls': '%{time_appconnect}',
            'ttfb': '%{time_starttransfer}',
            'total': '%{time_total}',
            'code': '%{http_code}',
            'ip': '%{remote_ip}',
        })

        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', fmt,
             '--max-time', str(timeout), '-L', url],
            capture_output=True, text=True, timeout=timeout + 5
        )

        if result.returncode != 0:
            return HTTPProbeResult(success=False, error=f'curl failed: {result.stderr.strip()}')

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return HTTPProbeResult(success=False, error='Failed to parse curl output')

        dns_time = float(data.get('dns', 0)) * 1000
        tcp_connect = float(data.get('tcp', 0)) * 1000
        tls_time_raw = float(data.get('tls', 0)) * 1000
        ttfb = float(data.get('ttfb', 0)) * 1000
        total = float(data.get('total', 0)) * 1000
        status_code = int(data.get('code', 0))
        resolved_ip = data.get('ip', '')

        tcp_time = tcp_connect - dns_time if tcp_connect > dns_time else tcp_connect
        tls_time = tls_time_raw - tcp_connect if tls_time_raw > tcp_connect else 0

        return HTTPProbeResult(
            success=200 <= status_code < 400,
            status_code=status_code,
            dns_time=round(dns_time, 2),
            tcp_time=round(tcp_time, 2),
            tls_time=round(tls_time, 2),
            ttfb=round(ttfb, 2),
            total_time=round(total, 2),
            resolved_ip=resolved_ip if resolved_ip else None,
        )
    except subprocess.TimeoutExpired:
        return HTTPProbeResult(success=False, error='Request timed out')
    except Exception as e:
        return HTTPProbeResult(success=False, error=str(e))


def _probe_requests(url: str, timeout: int) -> HTTPProbeResult:
    """Fallback: use Python requests module."""
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

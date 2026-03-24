"""DNS 查询探测核心 — 基于 Network-Monitoring-Tools/dns_lookup 实现。

参考上游: Network-Monitoring-Tools/dns_lookup/monitor_dns.py
上游函数: resolve_dns_with_server()
probes/dns_probe.py 作为适配层调用本模块。
"""
import subprocess
import shutil
import re
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class DNSProbeResult:
    success: bool = False
    latency: Optional[float] = None
    resolved_ip: Optional[str] = None
    error: Optional[str] = None


def probe(target: str, port: int = None, timeout: int = 10) -> DNSProbeResult:
    """Execute DNS lookup probe.

    Aligned with upstream resolve_dns_with_server().
    Uses dig (preferred, same as upstream) with nslookup fallback.
    """
    if shutil.which('dig'):
        return _probe_dig(target, port, timeout)
    elif shutil.which('nslookup'):
        return _probe_nslookup(target, port, timeout)
    else:
        return DNSProbeResult(success=False, error='Neither dig nor nslookup available')


def _probe_dig(target: str, port: int, timeout: int) -> DNSProbeResult:
    """Use dig command, aligned with upstream resolve_dns_with_server()."""
    try:
        cmd = ['dig', '+short', f'+time={timeout}', '+tries=1', target]
        if port:
            cmd.extend(['-p', str(port)])

        start = time.time()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 2
        )
        elapsed = (time.time() - start) * 1000

        if result.returncode != 0:
            return DNSProbeResult(
                success=False,
                latency=round(elapsed, 2),
                error=f'DNS lookup failed: {result.stderr.strip()}'
            )

        output = result.stdout.strip()
        if not output:
            return DNSProbeResult(
                success=False,
                latency=round(elapsed, 2),
                error='DNS lookup returned no results'
            )

        resolved_ip = _parse_dig_output(output)
        return DNSProbeResult(
            success=True,
            latency=round(elapsed, 2),
            resolved_ip=resolved_ip,
        )
    except subprocess.TimeoutExpired:
        return DNSProbeResult(success=False, error='DNS lookup timed out')
    except Exception as e:
        return DNSProbeResult(success=False, error=str(e))


def _probe_nslookup(target: str, port: int, timeout: int) -> DNSProbeResult:
    """Fallback: use nslookup command."""
    try:
        cmd = ['nslookup', target]
        if port:
            cmd = ['nslookup', f'-port={port}', target]

        start = time.time()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 2
        )
        elapsed = (time.time() - start) * 1000

        if result.returncode != 0:
            return DNSProbeResult(
                success=False,
                latency=round(elapsed, 2),
                error=f'DNS lookup failed: {result.stderr.strip()}'
            )

        resolved_ip = _parse_nslookup_output(result.stdout)
        return DNSProbeResult(
            success=True,
            latency=round(elapsed, 2),
            resolved_ip=resolved_ip,
        )
    except subprocess.TimeoutExpired:
        return DNSProbeResult(success=False, error='DNS lookup timed out')
    except Exception as e:
        return DNSProbeResult(success=False, error=str(e))


def _parse_dig_output(output: str) -> Optional[str]:
    """Parse resolved IP from dig +short output."""
    for line in output.split('\n'):
        line = line.strip()
        if re.match(r'^[\d.]+$', line):
            return line
        if re.match(r'^[0-9a-fA-F:]+$', line):
            return line
    return output.split('\n')[0].strip() if output else None


def _parse_nslookup_output(output: str) -> Optional[str]:
    """Parse resolved IP from nslookup output."""
    lines = output.split('\n')
    in_answer = False
    for line in lines:
        if 'Name:' in line:
            in_answer = True
            continue
        if in_answer and 'Address:' in line:
            m = re.search(r'Address:\s*([\d.]+)', line)
            if m:
                return m.group(1)
            m = re.search(r'Address:\s*([0-9a-fA-F:]+)', line)
            if m:
                return m.group(1)
    return None

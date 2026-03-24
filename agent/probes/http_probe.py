"""HTTP/HTTPS probe plugin — adapter wrapping network_tools.curl_ping (Project 11.4)."""
import shutil
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.curl_ping import probe as http_probe_fn

logger = logging.getLogger(__name__)


class HTTPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'http'

    def self_test(self) -> bool:
        """Check curl is available or requests module can be imported."""
        if shutil.which('curl'):
            return True
        try:
            import requests
            return True
        except ImportError:
            pass
        self._test_error = 'curl command not available and requests module not installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'curl/requests not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        r = http_probe_fn(target, port=port, timeout=timeout)
        return ProbeResult(
            success=r.success,
            latency=r.total_time,
            status_code=r.status_code,
            dns_time=r.dns_time,
            tcp_time=r.tcp_time,
            tls_time=r.tls_time,
            ttfb=r.ttfb,
            total_time=r.total_time,
            resolved_ip=r.resolved_ip,
            error=r.error,
        )


register_probe('http', HTTPProbe)

"""HTTP/HTTPS probe — calls agent.tools.curl_ping directly."""
import shutil
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.curl_ping.monitor_curl import run_curl, normalize_url

logger = logging.getLogger(__name__)


class HTTPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'http'

    def self_test(self) -> bool:
        if shutil.which('curl'):
            return True
        try:
            import requests  # noqa
            return True
        except ImportError:
            pass
        self._test_error = 'curl command not available and requests module not installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'curl/requests not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            url = normalize_url(target)
            if port and ':' not in target.split('/')[-1]:
                # Inject port into URL
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(url)
                netloc = f'{parsed.hostname}:{port}'
                url = urlunparse(parsed._replace(netloc=netloc))
            result = run_curl(url)
            if not result.get('success'):
                return ProbeResult(success=False, error=result.get('error', 'curl failed'))
            return ProbeResult(
                success=True,
                latency=result.get('total_time'),
                status_code=int(result['http_code']) if result.get('http_code') else None,
                dns_time=result.get('dns_time'),
                tcp_time=result.get('connect_time'),
                tls_time=None,  # Computed as connect-dns if needed
                ttfb=result.get('transfer_time'),
                total_time=result.get('total_time'),
                resolved_ip=None,
            )
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('http', HTTPProbe)

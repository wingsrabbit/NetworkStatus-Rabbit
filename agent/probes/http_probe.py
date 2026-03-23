"""HTTP/HTTPS probe plugin."""
import subprocess
import shutil
import json
import time
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe

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
        # Build URL
        url = target
        if not url.startswith(('http://', 'https://')):
            scheme = 'https' if port == 443 else 'http'
            url = f'{scheme}://{target}'
            if port and port not in (80, 443):
                url = f'{scheme}://{target}:{port}'

        if shutil.which('curl'):
            return self._probe_curl(url, timeout)
        else:
            return self._probe_requests(url, timeout)

    def _probe_curl(self, url, timeout):
        """Use curl with timing info."""
        try:
            # curl write-out format for timing
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
                return ProbeResult(success=False, error=f'curl failed: {result.stderr.strip()}')

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                return ProbeResult(success=False, error=f'Failed to parse curl output')

            dns_time = float(data.get('dns', 0)) * 1000
            tcp_connect = float(data.get('tcp', 0)) * 1000
            tls_time_raw = float(data.get('tls', 0)) * 1000
            ttfb = float(data.get('ttfb', 0)) * 1000
            total = float(data.get('total', 0)) * 1000
            status_code = int(data.get('code', 0))
            resolved_ip = data.get('ip', '')

            tcp_time = tcp_connect - dns_time if tcp_connect > dns_time else tcp_connect
            tls_time = tls_time_raw - tcp_connect if tls_time_raw > tcp_connect else 0

            return ProbeResult(
                success=200 <= status_code < 400,
                latency=round(total, 2),
                status_code=status_code,
                dns_time=round(dns_time, 2),
                tcp_time=round(tcp_time, 2),
                tls_time=round(tls_time, 2),
                ttfb=round(ttfb, 2),
                total_time=round(total, 2),
                resolved_ip=resolved_ip if resolved_ip else None,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(success=False, error='Request timed out')
        except Exception as e:
            return ProbeResult(success=False, error=str(e))

    def _probe_requests(self, url, timeout):
        """Fallback: use Python requests module."""
        try:
            import requests
            start = time.time()
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
            total = (time.time() - start) * 1000

            return ProbeResult(
                success=200 <= resp.status_code < 400,
                latency=round(total, 2),
                status_code=resp.status_code,
                total_time=round(total, 2),
            )
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('http', HTTPProbe)

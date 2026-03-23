"""DNS Lookup probe plugin."""
import subprocess
import shutil
import re
import time
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe

logger = logging.getLogger(__name__)


class DNSProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'dns'

    def self_test(self) -> bool:
        """Check nslookup is available."""
        if shutil.which('nslookup'):
            return True
        self._test_error = 'nslookup command not installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'nslookup not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            start = time.time()
            cmd = ['nslookup', target]
            if port:
                cmd = ['nslookup', f'-port={port}', target]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout + 2
            )
            elapsed = (time.time() - start) * 1000

            if result.returncode != 0:
                return ProbeResult(
                    success=False,
                    dns_time=round(elapsed, 2),
                    error=f'DNS lookup failed: {result.stderr.strip()}'
                )

            # Parse resolved IP
            output = result.stdout
            resolved_ip = self._parse_ip(output)

            return ProbeResult(
                success=True,
                latency=round(elapsed, 2),
                dns_time=round(elapsed, 2),
                resolved_ip=resolved_ip,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(success=False, error='DNS lookup timed out')
        except Exception as e:
            return ProbeResult(success=False, error=str(e))

    def _parse_ip(self, output):
        """Parse resolved IP from nslookup output."""
        # Skip header (authoritative answers come after "Name:" line)
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
                # IPv6
                m = re.search(r'Address:\s*([0-9a-fA-F:]+)', line)
                if m:
                    return m.group(1)
        return None


register_probe('dns', DNSProbe)

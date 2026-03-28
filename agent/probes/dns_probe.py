"""DNS Lookup probe — calls agent.tools.dns_lookup directly."""
import shutil
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.dns_lookup.monitor_dns import resolve_dns_with_server

logger = logging.getLogger(__name__)


class DNSProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'dns'

    def self_test(self) -> bool:
        if shutil.which('dig'):
            return True
        if shutil.which('nslookup'):
            return True
        self._test_error = 'Neither dig nor nslookup command installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'dig/nslookup not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            dns_time_ms, resolved_ip, status, all_ips = resolve_dns_with_server(target, dns_server=None)
            latency = float(dns_time_ms) if dns_time_ms and dns_time_ms != 'N/A' else None
            return ProbeResult(
                success=status == 'SUCCESS',
                latency=latency,
                dns_time=latency,
                resolved_ip=resolved_ip if resolved_ip else None,
                error=None if status == 'SUCCESS' else status,
            )
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('dns', DNSProbe)

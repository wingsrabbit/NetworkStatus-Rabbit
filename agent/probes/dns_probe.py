"""DNS Lookup probe plugin — adapter wrapping network_tools.dns_lookup (Project 11.4)."""
import shutil
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.dns_lookup import probe as dns_probe_fn

logger = logging.getLogger(__name__)


class DNSProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'dns'

    def self_test(self) -> bool:
        """Check dig or nslookup is available."""
        if shutil.which('dig'):
            return True
        if shutil.which('nslookup'):
            return True
        self._test_error = 'Neither dig nor nslookup command installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'dig/nslookup not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        r = dns_probe_fn(target, port=port, timeout=timeout)
        return ProbeResult(
            success=r.success,
            latency=r.latency,
            dns_time=r.latency,
            resolved_ip=r.resolved_ip,
            error=r.error,
        )


register_probe('dns', DNSProbe)

"""UDP Ping probe plugin — adapter wrapping network_tools.udp_ping (Project 11.4)."""
import shutil
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.udp_ping import ping as udp_ping

logger = logging.getLogger(__name__)


class UDPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'udp'

    def self_test(self) -> bool:
        """Check nc (netcat) is available per PROJECT 11.5."""
        if shutil.which('nc'):
            return True
        self._test_error = 'nc (netcat) not installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'nc (netcat) not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        r = udp_ping(target, port=port or 53, count=5, timeout=timeout)
        return ProbeResult(
            success=r.success,
            latency=r.latency,
            packet_loss=r.packet_loss,
            jitter=r.jitter,
            error=r.error,
        )


register_probe('udp', UDPProbe)

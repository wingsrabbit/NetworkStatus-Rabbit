"""UDP Ping probe plugin — adapter wrapping network_tools.udp_ping (Project 11.4)."""
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.udp_ping import ping as udp_ping

logger = logging.getLogger(__name__)


class UDPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'udp'

    def self_test(self) -> bool:
        """UDP uses Python socket — always available."""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.close()
            return True
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'Python socket (SOCK_DGRAM) not available')

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

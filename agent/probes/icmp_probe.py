"""ICMP Ping probe plugin — adapter wrapping network_tools.icmp_ping (Project 11.4)."""
import platform
import subprocess
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.icmp_ping import ping as icmp_ping

logger = logging.getLogger(__name__)


class ICMPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'icmp'

    def self_test(self) -> bool:
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', '127.0.0.1'] if platform.system() != 'Windows'
                else ['ping', '-n', '1', '-w', '2000', '127.0.0.1'],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'ping command not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        r = icmp_ping(target, count=1, timeout=timeout)
        return ProbeResult(
            success=r.success,
            latency=r.latency,
            packet_loss=r.packet_loss,
            error=r.error,
        )


register_probe('icmp', ICMPProbe)

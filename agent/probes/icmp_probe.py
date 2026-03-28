"""ICMP Ping probe — calls agent.tools.icmp_ping directly."""
import platform
import subprocess
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.icmp_ping.monitor_ping import run_ping, parse_ping_output

logger = logging.getLogger(__name__)


class ICMPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'icmp'

    def self_test(self) -> bool:
        try:
            cmd = (['ping', '-c', '1', '-W', '2', '127.0.0.1']
                   if platform.system() != 'Windows'
                   else ['ping', '-n', '1', '-w', '2000', '127.0.0.1'])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'ping command not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            output, is_error = run_ping(target, count=1, timeout=timeout)
            if is_error:
                return ProbeResult(success=False, packet_loss=100.0, error=output[:200])
            tx, rx, loss_str, min_rtt, avg_rtt, max_rtt, stddev_rtt, parse_error = parse_ping_output(output, 1)
            loss = float(loss_str) if loss_str and loss_str != 'N/A' else 100.0
            latency = float(avg_rtt) if avg_rtt and avg_rtt != 'N/A' else None
            return ProbeResult(
                success=loss < 100.0,
                latency=latency,
                packet_loss=loss,
            )
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('icmp', ICMPProbe)

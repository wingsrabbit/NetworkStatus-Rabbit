"""TCP Ping probe — calls agent.tools.tcp_ping directly."""
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.tcp_ping.monitor_tcp_ping import tcp_connect_single

logger = logging.getLogger(__name__)


class TCPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'tcp'

    def self_test(self) -> bool:
        try:
            import socket
            sock = socket.create_connection(('127.0.0.1', 0), timeout=1)
            sock.close()
            return True
        except (ConnectionRefusedError, OSError):
            return True
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'Python socket module not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            success, rtt_ms, error_msg = tcp_connect_single(target, port or 80, timeout)
            return ProbeResult(
                success=success,
                latency=rtt_ms,
                tcp_time=rtt_ms,
                error=error_msg,
            )
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('tcp', TCPProbe)

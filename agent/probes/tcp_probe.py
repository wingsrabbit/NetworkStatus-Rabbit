"""TCP Ping probe plugin."""
import socket
import time
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe

logger = logging.getLogger(__name__)


class TCPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'tcp'

    def self_test(self) -> bool:
        """Check Python socket module is available and create_connection callable."""
        try:
            import socket as s
            assert hasattr(s, 'create_connection')
            return True
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'Python socket module not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        if port is None:
            port = 80

        try:
            start = time.time()
            sock = socket.create_connection((target, port), timeout=timeout)
            elapsed = (time.time() - start) * 1000  # ms
            sock.close()

            return ProbeResult(
                success=True,
                latency=round(elapsed, 2),
                tcp_time=round(elapsed, 2),
            )
        except socket.timeout:
            return ProbeResult(success=False, error='Connection timed out')
        except ConnectionRefusedError:
            return ProbeResult(success=False, error=f'Connection refused on port {port}')
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('tcp', TCPProbe)

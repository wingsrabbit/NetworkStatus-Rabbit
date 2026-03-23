"""UDP Ping probe plugin."""
import subprocess
import shutil
import time
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe

logger = logging.getLogger(__name__)


class UDPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'udp'

    def self_test(self) -> bool:
        """Check nc (netcat) is available."""
        if shutil.which('nc'):
            return True
        self._test_error = 'nc (netcat) not installed'
        return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'nc (netcat) not installed')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        if port is None:
            port = 53

        try:
            start = time.time()
            # Use nc to send empty UDP packet
            result = subprocess.run(
                ['nc', '-u', '-z', '-w', str(timeout), target, str(port)],
                capture_output=True, text=True, timeout=timeout + 2
            )
            elapsed = (time.time() - start) * 1000

            success = result.returncode == 0
            return ProbeResult(
                success=success,
                latency=round(elapsed, 2) if success else None,
                error=result.stderr.strip() if not success else None,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(success=False, error='Request timed out')
        except Exception as e:
            return ProbeResult(success=False, error=str(e))


register_probe('udp', UDPProbe)

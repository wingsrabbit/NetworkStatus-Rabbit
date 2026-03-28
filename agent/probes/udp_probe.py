"""UDP Ping probe — calls agent.tools.udp_ping directly."""
import logging
import math
import socket as _socket

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.udp_ping.ping_udp import _perform_ping_batch

logger = logging.getLogger(__name__)


class UDPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'udp'

    def self_test(self) -> bool:
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            sock.close()
            return True
        except OSError as exc:
            self._test_error = f'UDP socket unavailable: {exc}'
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'UDP socket unavailable')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            resolved = _socket.gethostbyname(target)
            target_addr = (resolved, port or 9192)
            results, loss_pct, rtt_min, rtt_avg, rtt_max, rtt_stdev, jitter, duration = \
                _perform_ping_batch(target_addr, batch_count=5, interval=0.2,
                                    timeout=timeout, payload_size=64,
                                    buffer_size=1024, verbose=False)
            success = loss_pct < 100.0
            latency = rtt_avg if success and not math.isnan(rtt_avg) else None
            jit = jitter if success and not math.isnan(jitter) else None
            return ProbeResult(
                success=success,
                latency=latency,
                packet_loss=loss_pct,
                jitter=jit,
            )
        except Exception as e:
            return ProbeResult(success=False, packet_loss=100.0, error=str(e))


register_probe('udp', UDPProbe)

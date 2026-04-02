"""MTR probe — supports ICMP, TCP, and UDP sub-protocols."""
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.tools.mtr.monitor_mtr import run_mtr, check_mtr_available

logger = logging.getLogger(__name__)


class _MtrProbeBase(BaseProbe):
    """Base class for MTR probes with ICMP/TCP/UDP variants."""

    _mtr_protocol: str = 'icmp'

    def self_test(self) -> bool:
        ok, reason = check_mtr_available()
        if not ok:
            self._test_error = reason
        return ok

    def self_test_reason(self):
        return getattr(self, '_test_error', 'mtr command not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        try:
            mtr_result = run_mtr(
                target,
                protocol=self._mtr_protocol,
                port=port,
                count=1,
                timeout=timeout,
            )

            if not mtr_result.success or not mtr_result.hops:
                return ProbeResult(success=False, error=mtr_result.error)

            # Extract summary metrics from the final hop (destination)
            final_hop = mtr_result.hops[-1]
            latency = final_hop.avg if final_hop.avg > 0 else None
            packet_loss = final_hop.loss_percent
            jitter = final_hop.stdev if final_hop.stdev > 0 else None

            # Build hops list for the result
            hops_data = []
            for h in mtr_result.hops:
                hops_data.append({
                    'hop': h.hop,
                    'host': h.host,
                    'loss': h.loss_percent,
                    'sent': h.sent,
                    'last': h.last,
                    'avg': h.avg,
                    'best': h.best,
                    'worst': h.worst,
                    'stdev': h.stdev,
                })

            result = ProbeResult(
                success=packet_loss < 100.0,
                latency=latency,
                packet_loss=packet_loss,
                jitter=jitter,
            )
            result.hops = hops_data
            result.extra = {
                'mtr_src': mtr_result.src,
                'mtr_dst': mtr_result.dst,
            }
            return result

        except Exception as e:
            return ProbeResult(success=False, error=str(e))


class MtrIcmpProbe(_MtrProbeBase):
    _mtr_protocol = 'icmp'

    def protocol_name(self) -> str:
        return 'mtr_icmp'


class MtrTcpProbe(_MtrProbeBase):
    _mtr_protocol = 'tcp'

    def protocol_name(self) -> str:
        return 'mtr_tcp'


class MtrUdpProbe(_MtrProbeBase):
    _mtr_protocol = 'udp'

    def protocol_name(self) -> str:
        return 'mtr_udp'


register_probe('mtr_icmp', MtrIcmpProbe)
register_probe('mtr_tcp', MtrTcpProbe)
register_probe('mtr_udp', MtrUdpProbe)

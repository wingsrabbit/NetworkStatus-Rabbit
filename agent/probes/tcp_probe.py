"""TCP Ping probe plugin — adapter wrapping network_tools.tcp_ping (Project 11.4).

探测核心参考上游: Network-Monitoring-Tools/tcp_ping/monitor_tcp_ping.py"""
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe
from agent.network_tools.tcp_ping import ping as tcp_ping

logger = logging.getLogger(__name__)


class TCPProbe(BaseProbe):

    def protocol_name(self) -> str:
        return 'tcp'

    def self_test(self) -> bool:
        try:
            import socket
            # 验证 socket 模块可导入且 create_connection 可正常调用
            sock = socket.create_connection(('127.0.0.1', 0), timeout=1)
            sock.close()
            return True
        except (ConnectionRefusedError, OSError):
            # 连接被拒绝或端口不可达说明 socket 功能本身正常
            return True
        except Exception as e:
            self._test_error = str(e)
            return False

    def self_test_reason(self):
        return getattr(self, '_test_error', 'Python socket module not available')

    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        r = tcp_ping(target, port=port or 80, timeout=timeout)
        return ProbeResult(
            success=r.success,
            latency=r.latency,
            tcp_time=r.latency,
            error=r.error,
        )


register_probe('tcp', TCPProbe)

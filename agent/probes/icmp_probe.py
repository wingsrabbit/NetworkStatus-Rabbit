"""ICMP Ping probe plugin."""
import platform
import subprocess
import re
import logging

from agent.probes.base import BaseProbe, ProbeResult, register_probe

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
        try:
            is_windows = platform.system() == 'Windows'
            # 单次探测：每轮只发 1 个 echo request，与 tcp/udp/http/dns 统一
            count = 1
            if is_windows:
                cmd = ['ping', '-n', str(count), '-w', str(timeout * 1000), target]
            else:
                cmd = ['ping', '-c', str(count), '-W', str(timeout), target]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            output = result.stdout

            if result.returncode != 0:
                return ProbeResult(success=False, packet_loss=100.0,
                                   error=f'ping failed: {result.stderr.strip()}')

            # Parse latency
            latency = self._parse_avg_latency(output)
            packet_loss = self._parse_packet_loss(output)
            jitter = self._parse_jitter(output)

            return ProbeResult(
                success=True,
                latency=latency,
                packet_loss=packet_loss,
                jitter=jitter,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(success=False, error='Request timed out')
        except Exception as e:
            return ProbeResult(success=False, error=str(e))

    def _parse_avg_latency(self, output):
        # Linux: rtt min/avg/max/mdev = 0.030/0.045/0.060/0.015 ms
        m = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms', output)
        if m:
            return float(m.group(1))
        # Windows: Average = 12ms
        m = re.search(r'Average = (\d+)ms', output)
        if m:
            return float(m.group(1))
        # Alternative: time=12.5 ms
        times = re.findall(r'time[=<](\d+\.?\d*)\s*ms', output)
        if times:
            return sum(float(t) for t in times) / len(times)
        return None

    def _parse_packet_loss(self, output):
        m = re.search(r'(\d+)% packet loss', output)
        if m:
            return float(m.group(1))
        m = re.search(r'(\d+)% loss', output)
        if m:
            return float(m.group(1))
        return 0.0

    def _parse_jitter(self, output):
        # Linux: rtt min/avg/max/mdev = 0.030/0.045/0.060/0.015 ms
        m = re.search(r'rtt min/avg/max/mdev = [\d.]+/[\d.]+/[\d.]+/([\d.]+) ms', output)
        if m:
            return float(m.group(1))
        return None


register_probe('icmp', ICMPProbe)

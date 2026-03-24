"""UDP Ping 探测核心 — 基于 socket 的真实 RTT / 丢包 / 抖动测量。

发送多个 UDP 数据报并测量响应（ICMP 或 UDP 回复），
计算 RTT、packet_loss、jitter。

probes/udp_probe.py 作为适配层调用本模块。
"""
import socket
import time
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 探测包负载：16 字节标记
_PROBE_PAYLOAD = b'NSR-UDP-PROBE\x00\x00\x00'


@dataclass
class UDPPingResult:
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    jitter: Optional[float] = None
    rtts: list[float] = field(default_factory=list)
    error: Optional[str] = None


def ping(target: str, port: int = 53, count: int = 5,
         timeout: int = 10, interval: float = 0.2) -> UDPPingResult:
    """Send count UDP packets and measure RTT / loss / jitter.

    Approach:
    - Create UDP socket with per-packet timeout
    - Send probe payload, wait for any response
    - On ICMP unreachable → socket raises ConnectionRefusedError → port closed but reachable (count as success with RTT)
    - On actual UDP response → measure RTT normally
    - On timeout → packet considered lost

    Args:
        target:   Destination hostname or IP
        port:     Destination port (default 53 for DNS)
        count:    Number of packets to send
        timeout:  Overall timeout in seconds
        interval: Delay between sends in seconds
    """
    per_packet_timeout = min(timeout / max(count, 1), 2.0)

    rtts: list[float] = []
    sent = 0
    received = 0

    try:
        # Resolve hostname once
        addr_info = socket.getaddrinfo(target, port, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        if not addr_info:
            return UDPPingResult(success=False, error=f'Cannot resolve {target}')
        family, socktype, proto, _, sockaddr = addr_info[0]
    except socket.gaierror as e:
        return UDPPingResult(success=False, error=f'DNS resolution failed: {e}')

    for i in range(count):
        sent += 1
        try:
            sock = socket.socket(family, socket.SOCK_DGRAM)
            sock.settimeout(per_packet_timeout)

            start = time.perf_counter()
            sock.sendto(_PROBE_PAYLOAD, sockaddr)
            try:
                sock.recvfrom(1024)
                elapsed = (time.perf_counter() - start) * 1000
                rtts.append(elapsed)
                received += 1
            except ConnectionRefusedError:
                # ICMP port unreachable — host reachable, port closed
                elapsed = (time.perf_counter() - start) * 1000
                rtts.append(elapsed)
                received += 1
            except socket.timeout:
                # No response — count as lost
                pass
            finally:
                sock.close()
        except Exception as e:
            logger.debug(f'UDP probe packet {i+1}/{count} error: {e}')

        if i < count - 1:
            time.sleep(interval)

    if sent == 0:
        return UDPPingResult(success=False, error='No packets sent')

    loss = ((sent - received) / sent) * 100.0

    if not rtts:
        return UDPPingResult(
            success=False,
            packet_loss=100.0,
            error='All packets lost',
        )

    avg_rtt = sum(rtts) / len(rtts)
    jitter_val = None
    if len(rtts) >= 2:
        variance = sum((r - avg_rtt) ** 2 for r in rtts) / len(rtts)
        jitter_val = round(math.sqrt(variance), 2)

    return UDPPingResult(
        success=True,
        latency=round(avg_rtt, 2),
        packet_loss=round(loss, 2),
        jitter=jitter_val,
        rtts=rtts,
    )

"""UDP Ping 探测核心 — 基于 Network-Monitoring-Tools/udp_ping 实现。

参考上游: Network-Monitoring-Tools/udp_ping/ping_udp.py
上游函数: create_packet(), unpack_packet(), _perform_ping_batch()
probes/udp_probe.py 作为适配层调用本模块。
"""
import socket
import struct
import time
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Packet format aligned with upstream create_packet():
# Header: 4-byte sequence (unsigned int) + 8-byte timestamp (double)
_HEADER_FORMAT = '!Id'
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)
_DEFAULT_PAYLOAD_SIZE = 64


@dataclass
class UDPPingResult:
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    jitter: Optional[float] = None
    rtts: list[float] = field(default_factory=list)
    error: Optional[str] = None


def create_packet(seq_num: int, payload_size: int = _DEFAULT_PAYLOAD_SIZE) -> bytes:
    """Create UDP probe packet with timestamp header.

    Aligned with upstream create_packet(seq_num, payload_size).
    """
    header = struct.pack(_HEADER_FORMAT, seq_num, time.time())
    padding_size = max(0, payload_size - _HEADER_SIZE)
    return header + b'\x00' * padding_size


def unpack_packet(data: bytes):
    """Extract header from received packet.

    Aligned with upstream unpack_packet(data).
    Returns: (seq_num, timestamp, payload)
    """
    if len(data) < _HEADER_SIZE:
        return None, None, data
    seq_num, timestamp = struct.unpack(_HEADER_FORMAT, data[:_HEADER_SIZE])
    return seq_num, timestamp, data[_HEADER_SIZE:]


def ping(target: str, port: int = 53, count: int = 5,
         timeout: int = 10, interval: float = 0.2) -> UDPPingResult:
    """Send count UDP packets and measure RTT / loss / jitter.

    Aligned with upstream _perform_ping_batch() approach:
    - Create packets with sequence numbers and timestamps
    - Send via UDP socket, wait for response or ICMP unreachable
    - On timeout -> packet considered lost
    - Calculate RTT, packet_loss, jitter from results
    """
    per_packet_timeout = min(timeout / max(count, 1), 2.0)

    rtts: list[float] = []
    sent = 0
    received = 0

    try:
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

            packet = create_packet(i + 1)
            start = time.perf_counter()
            sock.sendto(packet, sockaddr)
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

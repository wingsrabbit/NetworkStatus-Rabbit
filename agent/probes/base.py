"""Probe plugin base class and registry (Section 11.2, 11.3)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

PROBE_REGISTRY = {}


@dataclass
class ProbeResult:
    """Unified probe result data structure."""
    success: bool = False
    latency: Optional[float] = None
    packet_loss: Optional[float] = None
    jitter: Optional[float] = None
    status_code: Optional[int] = None
    dns_time: Optional[float] = None
    tcp_time: Optional[float] = None
    tls_time: Optional[float] = None
    ttfb: Optional[float] = None
    total_time: Optional[float] = None
    resolved_ip: Optional[str] = None
    error: Optional[str] = None
    hops: Optional[list] = None
    extra: Optional[dict] = None

    def to_dict(self):
        d = {'success': self.success, 'error': self.error}
        for f in ['latency', 'packet_loss', 'jitter', 'status_code', 'dns_time',
                   'tcp_time', 'tls_time', 'ttfb', 'total_time', 'resolved_ip']:
            val = getattr(self, f)
            if val is not None:
                d[f] = val
        if self.hops is not None:
            d['hops'] = self.hops
        if self.extra is not None:
            d['extra'] = self.extra
        return d


class BaseProbe(ABC):
    """Probe plugin base class."""

    @abstractmethod
    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        """Execute a single probe and return the result."""
        pass

    @abstractmethod
    def protocol_name(self) -> str:
        """Return protocol name: 'icmp', 'tcp', 'udp', 'http', 'dns'."""
        pass

    def self_test(self) -> bool:
        """Self-test whether this protocol is available. Default: True."""
        return True

    def self_test_reason(self) -> Optional[str]:
        """Return reason if self-test failed."""
        return None


def register_probe(protocol: str, probe_class):
    PROBE_REGISTRY[protocol] = probe_class


def get_probe(protocol: str) -> Optional[BaseProbe]:
    cls = PROBE_REGISTRY.get(protocol)
    if cls:
        return cls()
    return None


def get_all_probes():
    return {name: cls() for name, cls in PROBE_REGISTRY.items()}

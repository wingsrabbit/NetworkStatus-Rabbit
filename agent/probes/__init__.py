"""Probe plugin registry - auto-import all probe modules."""
from agent.probes.base import PROBE_REGISTRY, get_probe, get_all_probes, register_probe

# Import all probe modules to trigger registration
from agent.probes import icmp_probe
from agent.probes import tcp_probe
from agent.probes import udp_probe
from agent.probes import http_probe
from agent.probes import dns_probe

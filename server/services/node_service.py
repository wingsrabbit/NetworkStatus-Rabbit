"""Node management service."""
import json
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory heartbeat tracking
# node_id -> list of (timestamp_second) for each received heartbeat
_heartbeat_windows = defaultdict(list)
# node_id -> sid (Socket.IO session id)
_node_connections = {}

WINDOW_SIZE = 120  # seconds
OFFLINE_THRESHOLD = 20  # <=20 heartbeats in window = offline


def record_heartbeat(node_id, seq=None):
    """Record a heartbeat from a node."""
    now = time.time()
    window = _heartbeat_windows[node_id]
    window.append(now)
    # Trim to window
    cutoff = now - WINDOW_SIZE
    _heartbeat_windows[node_id] = [t for t in window if t > cutoff]


def get_heartbeat_count(node_id):
    """Get the number of heartbeats in the current window."""
    now = time.time()
    cutoff = now - WINDOW_SIZE
    window = _heartbeat_windows.get(node_id, [])
    _heartbeat_windows[node_id] = [t for t in window if t > cutoff]
    return len(_heartbeat_windows[node_id])


def is_node_online(node_id):
    """Check if a node is online based on heartbeat count."""
    return get_heartbeat_count(node_id) > OFFLINE_THRESHOLD


def register_connection(node_id, sid):
    """Register a node's WebSocket connection."""
    _node_connections[node_id] = sid


def unregister_connection(node_id):
    """Unregister a node's WebSocket connection."""
    _node_connections.pop(node_id, None)


def get_connection_sid(node_id):
    """Get the Socket.IO session ID for a connected node."""
    return _node_connections.get(node_id)


def get_all_connected_nodes():
    """Get all currently connected node IDs."""
    return set(_node_connections.keys())


def clear_heartbeats(node_id):
    """Clear heartbeat data for a node."""
    _heartbeat_windows.pop(node_id, None)

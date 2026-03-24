"""Task management service."""
import logging
import time
from threading import Lock

from server.extensions import db
from server.models.node import Node
from server.models.task import ProbeTask

logger = logging.getLogger(__name__)

# Task sync state machine
# node_id -> {config_version, retry_count, last_sent_at, state}
# state: 'pending' | 'synced' | 'desync'
_sync_state: dict[str, dict] = {}
_sync_lock = Lock()

SYNC_TIMEOUT = 30       # seconds before retry
SYNC_MAX_RETRIES = 3    # max retry attempts before desync


def get_tasks_for_node(node_id):
    """Get all enabled tasks for a specific node."""
    tasks = ProbeTask.query.filter_by(
        source_node_id=node_id,
        enabled=True
    ).all()
    return tasks


def increment_config_version(node_id):
    """Increment the config_version for a node.

    Only modifies the node object in the current session.
    The caller is responsible for committing the transaction.
    """
    node = db.session.get(Node, node_id)
    if node:
        node.config_version += 1
        return node.config_version
    return None


def get_config_version(node_id):
    """Get the current config_version for a node."""
    node = db.session.get(Node, node_id)
    return node.config_version if node else None


def mark_sync_pending(node_id: str, config_version: int):
    """Mark a sync as pending for a node."""
    with _sync_lock:
        _sync_state[node_id] = {
            'config_version': config_version,
            'retry_count': 0,
            'last_sent_at': time.time(),
            'state': 'pending',
        }


def mark_sync_acked(node_id: str, acked_version: int):
    """Mark sync as acknowledged for a node."""
    with _sync_lock:
        state = _sync_state.get(node_id)
        if state and state['config_version'] <= acked_version:
            state['state'] = 'synced'
            logger.info(f"Node {node_id} synced at version {acked_version}")
        elif state:
            logger.warning(f"Node {node_id} acked version {acked_version} but pending version is {state['config_version']}")


def mark_sync_desync(node_id: str):
    """Mark a node as desync."""
    with _sync_lock:
        if node_id in _sync_state:
            _sync_state[node_id]['state'] = 'desync'
            logger.warning(f"Node {node_id} marked as desync")


def is_desync(node_id: str) -> bool:
    """Check if a node is in desync state."""
    with _sync_lock:
        state = _sync_state.get(node_id)
        return state is not None and state['state'] == 'desync'


def clear_sync_state(node_id: str):
    """Clear sync state for a node (e.g. on disconnect)."""
    with _sync_lock:
        _sync_state.pop(node_id, None)


def check_pending_syncs():
    """Check for timed-out pending syncs and retry or mark desync.
    Should be called periodically from a background task.
    Returns list of (node_id, config_version) that need retry.
    """
    now = time.time()
    retries = []
    with _sync_lock:
        for node_id, state in list(_sync_state.items()):
            if state['state'] != 'pending':
                continue
            if now - state['last_sent_at'] >= SYNC_TIMEOUT:
                if state['retry_count'] < SYNC_MAX_RETRIES:
                    state['retry_count'] += 1
                    state['last_sent_at'] = now
                    retries.append((node_id, state['config_version']))
                    logger.info(f"Retrying sync for node {node_id} (attempt {state['retry_count']})")
                else:
                    state['state'] = 'desync'
                    logger.warning(f"Node {node_id} marked desync after {SYNC_MAX_RETRIES} retries")
    return retries

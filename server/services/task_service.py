"""Task management service."""
import logging

from server.extensions import db
from server.models.node import Node
from server.models.task import ProbeTask

logger = logging.getLogger(__name__)


def get_tasks_for_node(node_id):
    """Get all enabled tasks for a specific node."""
    tasks = ProbeTask.query.filter_by(
        source_node_id=node_id,
        enabled=True
    ).all()
    return tasks


def increment_config_version(node_id):
    """Increment the config_version for a node."""
    node = db.session.get(Node, node_id)
    if node:
        node.config_version += 1
        db.session.commit()
        return node.config_version
    return None


def get_config_version(node_id):
    """Get the current config_version for a node."""
    node = db.session.get(Node, node_id)
    return node.config_version if node else None

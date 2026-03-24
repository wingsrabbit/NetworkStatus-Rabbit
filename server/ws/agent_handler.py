"""Agent WebSocket handler - /agent namespace.

Handles: agent:auth, agent:heartbeat, agent:probe_result, agent:probe_batch, agent:task_ack
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone

import bcrypt
from flask import request as flask_request
from flask_socketio import Namespace, disconnect, emit

from server.extensions import db
from server.models.node import Node
from server.models.task import ProbeTask
from server.services import node_service, task_service
from server.services.influx_service import influx_service

logger = logging.getLogger(__name__)

# Track authenticated agent sessions: sid -> node_id
_agent_sessions = {}
# Track task_ack retries: node_id -> {config_version, retry_count, last_sent}
_task_ack_pending = {}

# Latest probe result per task (for dashboard snapshot + REST)
# key: task_id -> { latency, packet_loss, jitter, success, status_code, timestamp, ... }
_latest_results: dict[str, dict] = {}
_latest_lock = threading.Lock()


def get_latest_results() -> dict[str, dict]:
    """Get a snapshot of latest probe results per task for dashboard."""
    with _latest_lock:
        return dict(_latest_results)


def _update_latest_result(task_id: str, metrics: dict, timestamp=None):
    """Update the latest probe result cache for a task."""
    with _latest_lock:
        _latest_results[task_id] = {
            'latency': metrics.get('latency'),
            'packet_loss': metrics.get('packet_loss'),
            'jitter': metrics.get('jitter'),
            'success': metrics.get('success'),
            'status_code': metrics.get('status_code'),
            'timestamp': timestamp,
        }


class AgentNamespace(Namespace):

    def trigger_event(self, event, *args):
        """Map colon-delimited event names to underscore handler methods.
        e.g. 'agent:auth' -> on_agent_auth()
        Only intercept events containing ':', let connect/disconnect go through parent.
        """
        if ':' in event:
            handler_name = 'on_' + event.replace(':', '_')
            handler = getattr(self, handler_name, None)
            if handler:
                return handler(*args)
        return super().trigger_event(event, *args)

    def on_connect(self):
        sid = flask_request.sid
        logger.info(f"Agent connected: sid={sid}")

    def on_disconnect(self):
        sid = flask_request.sid
        node_id = _agent_sessions.pop(sid, None)
        if node_id:
            node_service.unregister_connection(node_id)
            task_service.clear_sync_state(node_id)
            logger.info(f"Agent disconnected: node_id={node_id}")

    def on_agent_auth(self, data):
        """Handle agent authentication."""
        sid = flask_request.sid
        node_id = data.get('node_id')
        token = data.get('token')
        client_config_version = data.get('config_version', 0)
        capabilities = data.get('capabilities', {})

        if not node_id or not token:
            emit('center:auth_result', {'success': False, 'message': 'Missing node_id or token'})
            disconnect()
            return

        node = db.session.get(Node, node_id)
        if not node:
            emit('center:auth_result', {'success': False, 'message': 'Node not found'})
            disconnect()
            return

        if not node.enabled:
            emit('center:auth_result', {'success': False, 'message': 'Node is disabled'})
            disconnect()
            return

        # Verify token
        if not bcrypt.checkpw(token.encode('utf-8'), node.token.encode('utf-8')):
            emit('center:auth_result', {'success': False, 'message': 'Invalid token'})
            disconnect()
            return

        # Authentication success
        _agent_sessions[sid] = node_id
        node_service.register_connection(node_id, sid)

        # Update node info
        now = datetime.now(timezone.utc)
        node.status = 'online'
        node.last_seen = now
        node.agent_version = capabilities.get('agent_version')
        node.public_ip = capabilities.get('public_ip')
        node.private_ip = capabilities.get('private_ip')
        node.capabilities = json.dumps(capabilities) if capabilities else None
        db.session.commit()

        emit('center:auth_result', {'success': True, 'message': 'Authenticated'})
        logger.info(f"Agent authenticated: node_id={node_id}, capabilities={capabilities.get('protocols', [])}")

        # Config version sync
        server_version = node.config_version
        if client_config_version != server_version or task_service.is_desync(node_id):
            if client_config_version > server_version:
                logger.warning(f"Node {node_id} has higher config_version ({client_config_version}) "
                               f"than server ({server_version}). Forcing full sync.")
            # Send full task sync
            tasks = task_service.get_tasks_for_node(node_id)
            emit('center:task_sync', {
                'config_version': server_version,
                'tasks': [t.to_agent_dict() for t in tasks]
            })
            task_service.mark_sync_pending(node_id, server_version)
        # else: versions match, no sync needed

    def on_agent_heartbeat(self, data):
        """Handle agent heartbeat (1/sec).
        Only update in-memory state; last_seen is batch-flushed by background task (BUG-B05).
        """
        sid = flask_request.sid
        node_id = _agent_sessions.get(sid)
        if not node_id:
            return

        node_service.record_heartbeat(node_id, data.get('seq'))

    def on_agent_probe_result(self, data):
        """Handle a single probe result."""
        sid = flask_request.sid
        node_id = _agent_sessions.get(sid)
        if not node_id:
            return

        result_id = data.get('result_id')
        task_id = data.get('task_id')

        # Get task info for tags
        task = db.session.get(ProbeTask, task_id)
        if not task:
            logger.warning(f"Probe result for unknown task: {task_id}")
            emit('center:result_ack', {'result_id': result_id})
            return

        # BUG-B03: Verify task belongs to this node
        if task.source_node_id != node_id:
            logger.warning(f"Node {node_id} submitted result for task {task_id} owned by {task.source_node_id}")
            emit('center:result_ack', {'result_id': result_id})
            return

        # BUG-01: Dedup check before writing
        if influx_service.check_result_exists(result_id, task_id):
            logger.debug(f"Duplicate result_id={result_id}, skipping write but ACKing")
            emit('center:result_ack', {'result_id': result_id})
            return

        source_node = db.session.get(Node, task.source_node_id)
        target_name = task.target_address
        if task.target_type == 'internal' and task.target_node_id:
            target_node = db.session.get(Node, task.target_node_id)
            target_name = target_node.name if target_node else task.target_node_id

        # Write to InfluxDB with result_id for dedup
        try:
            influx_service.write_probe_result({
                'task_id': task_id,
                'result_id': result_id,
                'source_node': source_node.name if source_node else node_id,
                'target': target_name or '',
                'protocol': data.get('protocol', task.protocol),
                'timestamp': data.get('timestamp'),
                'metrics': data.get('metrics', {}),
            })
            influx_service.mark_result_written(result_id)
        except Exception as e:
            logger.error(f"Failed to write probe result: {e}")

        # ACK
        emit('center:result_ack', {'result_id': result_id})

        # Update latest result cache for dashboard
        _update_latest_result(task_id, data.get('metrics', {}), data.get('timestamp'))

        # Push to dashboard subscribers — flatten metrics into ProbeResult shape
        from server.ws.dashboard_handler import push_task_detail
        metrics = data.get('metrics', {})
        flat_result = {
            'timestamp': data.get('timestamp'),
            'latency': metrics.get('latency'),
            'packet_loss': metrics.get('packet_loss'),
            'jitter': metrics.get('jitter'),
            'success': metrics.get('success'),
            'status_code': metrics.get('status_code'),
            'dns_time': metrics.get('dns_time'),
            'tcp_time': metrics.get('tcp_time'),
            'tls_time': metrics.get('tls_time'),
            'ttfb': metrics.get('ttfb'),
            'total_time': metrics.get('total_time'),
            'resolved_ip': metrics.get('resolved_ip'),
        }
        push_task_detail(task_id, flat_result)

        # BUG-A04: Only evaluate alerts for recent data (within 60s)
        is_recent = _is_recent_result(data.get('timestamp'))
        if is_recent:
            from server.services.alert_service import process_probe_result
            try:
                process_probe_result(task_id, data.get('metrics', {}))
            except Exception as e:
                logger.error(f"Alert evaluation failed for task {task_id}: {e}")

    def on_agent_probe_batch(self, data):
        """Handle batch probe results (backfill after reconnect).
        Backfill data is only stored, never triggers alerts (BUG-A04).
        """
        sid = flask_request.sid
        node_id = _agent_sessions.get(sid)
        if not node_id:
            return

        batch_id = data.get('batch_id')
        results = data.get('results', [])
        accepted_ids = []

        for result in results:
            result_id = result.get('result_id')
            task_id = result.get('task_id')

            task = db.session.get(ProbeTask, task_id)
            if not task:
                accepted_ids.append(result_id)
                continue

            # BUG-B03: Verify task belongs to this node
            if task.source_node_id != node_id:
                accepted_ids.append(result_id)
                continue

            # BUG-01: Dedup check
            if influx_service.check_result_exists(result_id, task_id):
                accepted_ids.append(result_id)
                continue

            source_node = db.session.get(Node, task.source_node_id)
            target_name = task.target_address
            if task.target_type == 'internal' and task.target_node_id:
                target_node = db.session.get(Node, task.target_node_id)
                target_name = target_node.name if target_node else task.target_node_id

            try:
                influx_service.write_probe_result({
                    'task_id': task_id,
                    'result_id': result_id,
                    'source_node': source_node.name if source_node else node_id,
                    'target': target_name or '',
                    'protocol': result.get('protocol', task.protocol),
                    'timestamp': result.get('timestamp'),
                    'metrics': result.get('metrics', {}),
                })
                influx_service.mark_result_written(result_id)
                accepted_ids.append(result_id)
            except Exception as e:
                logger.error(f"Failed to write batch result {result_id}: {e}")

        emit('center:batch_ack', {
            'batch_id': batch_id,
            'accepted_ids': accepted_ids
        })

    def on_agent_task_ack(self, data):
        """Handle task acknowledgment from agent."""
        sid = flask_request.sid
        node_id = _agent_sessions.get(sid)
        if not node_id:
            return

        acked_version = data.get('config_version')
        logger.info(f"Node {node_id} acknowledged config_version={acked_version}")
        task_service.mark_sync_acked(node_id, acked_version)
        _task_ack_pending.pop(node_id, None)


def _is_recent_result(timestamp) -> bool:
    """Check if a probe result timestamp is within 60 seconds of now."""
    if not timestamp:
        return True
    try:
        if isinstance(timestamp, str):
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            delta = (datetime.now(timezone.utc) - ts).total_seconds()
        elif isinstance(timestamp, (int, float)):
            delta = time.time() - timestamp
        else:
            return True
        return abs(delta) <= 60
    except Exception:
        return True


def register_agent_handlers(socketio):
    socketio.on_namespace(AgentNamespace('/agent'))

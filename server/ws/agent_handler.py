"""Agent WebSocket handler - /agent namespace.

Handles: agent:auth, agent:heartbeat, agent:probe_result, agent:probe_batch, agent:task_ack
"""
import json
import logging
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


class AgentNamespace(Namespace):

    def on_connect(self):
        sid = flask_request.sid
        logger.info(f"Agent connected: sid={sid}")

    def on_disconnect(self):
        sid = flask_request.sid
        node_id = _agent_sessions.pop(sid, None)
        if node_id:
            node_service.unregister_connection(node_id)
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
        if client_config_version < server_version or client_config_version > server_version:
            if client_config_version > server_version:
                logger.warning(f"Node {node_id} has higher config_version ({client_config_version}) "
                               f"than server ({server_version}). Forcing full sync.")
            # Send full task sync
            tasks = task_service.get_tasks_for_node(node_id)
            emit('center:task_sync', {
                'config_version': server_version,
                'tasks': [t.to_agent_dict() for t in tasks]
            })
        # else: versions match, no sync needed

    def on_agent_heartbeat(self, data):
        """Handle agent heartbeat (1/sec)."""
        sid = flask_request.sid
        node_id = _agent_sessions.get(sid)
        if not node_id:
            return

        node_service.record_heartbeat(node_id, data.get('seq'))

        # Update last_seen
        node = db.session.get(Node, node_id)
        if node:
            node.last_seen = datetime.now(timezone.utc)
            db.session.commit()

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

        source_node = db.session.get(Node, task.source_node_id)
        target_name = task.target_address
        if task.target_type == 'internal' and task.target_node_id:
            target_node = db.session.get(Node, task.target_node_id)
            target_name = target_node.name if target_node else task.target_node_id

        # Write to InfluxDB (idempotent - same tags+timestamp = overwrite)
        try:
            influx_service.write_probe_result({
                'task_id': task_id,
                'source_node': source_node.name if source_node else node_id,
                'target': target_name or '',
                'protocol': data.get('protocol', task.protocol),
                'timestamp': data.get('timestamp'),
                'metrics': data.get('metrics', {}),
            })
        except Exception as e:
            logger.error(f"Failed to write probe result: {e}")

        # ACK
        emit('center:result_ack', {'result_id': result_id})

        # Push to dashboard subscribers
        from server.ws.dashboard_handler import push_task_detail
        push_task_detail(task_id, data)

        # Alert evaluation
        from server.services.alert_service import process_probe_result
        try:
            process_probe_result(task_id, data.get('metrics', {}))
        except Exception as e:
            logger.error(f"Alert evaluation failed for task {task_id}: {e}")

    def on_agent_probe_batch(self, data):
        """Handle batch probe results (backfill after reconnect)."""
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

            source_node = db.session.get(Node, task.source_node_id)
            target_name = task.target_address
            if task.target_type == 'internal' and task.target_node_id:
                target_node = db.session.get(Node, task.target_node_id)
                target_name = target_node.name if target_node else task.target_node_id

            try:
                influx_service.write_probe_result({
                    'task_id': task_id,
                    'source_node': source_node.name if source_node else node_id,
                    'target': target_name or '',
                    'protocol': result.get('protocol', task.protocol),
                    'timestamp': result.get('timestamp'),
                    'metrics': result.get('metrics', {}),
                })
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
        _task_ack_pending.pop(node_id, None)


def register_agent_handlers(socketio):
    socketio.on_namespace(AgentNamespace('/agent'))

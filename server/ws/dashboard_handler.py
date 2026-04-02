"""Dashboard WebSocket handler - handles frontend real-time push.

Events: dashboard:subscribe_task, dashboard:unsubscribe_task, dashboard:probe_snapshot,
        dashboard:task_detail, dashboard:node_status, dashboard:alert
"""
import logging

from flask import request as flask_request
from flask_jwt_extended import decode_token
from flask_socketio import Namespace, disconnect, emit, join_room, leave_room

from server.extensions import socketio

logger = logging.getLogger(__name__)

# Track dashboard sessions: sid -> user_id
_dashboard_sessions = {}


class DashboardNamespace(Namespace):

    def trigger_event(self, event, *args):
        """Map colon-delimited event names to underscore handler methods.
        e.g. 'dashboard:subscribe_task' -> on_dashboard_subscribe_task()
        Uses socketio._handle_event to ensure Flask request context is set up.
        """
        if ':' in event:
            handler_name = 'on_' + event.replace(':', '_')
            handler = getattr(self, handler_name, None)
            if handler:
                return self.socketio._handle_event(
                    handler, event, self.namespace, *args)
        return super().trigger_event(event, *args)

    def on_connect(self):
        sid = flask_request.sid
        # Authenticate via httpOnly Cookie
        cookies = flask_request.cookies
        access_token = cookies.get('access_token_cookie')
        if not access_token:
            logger.warning(f"Dashboard connection rejected: no cookie, sid={sid}")
            raise ConnectionRefusedError({
                'code': 'WS_AUTH_FAILED',
                'message': 'Cookie 中的 JWT 无效或缺失'
            })
        try:
            decoded = decode_token(access_token)
            user_id = decoded.get('sub')
            _dashboard_sessions[sid] = user_id
            logger.info(f"Dashboard connected: sid={sid}, user_id={user_id}")
        except Exception as e:
            logger.warning(f"Dashboard connection rejected: invalid JWT, sid={sid}, error={e}")
            raise ConnectionRefusedError({
                'code': 'WS_AUTH_FAILED',
                'message': 'Cookie 中的 JWT 无效或已过期'
            })

    def on_disconnect(self):
        sid = flask_request.sid
        user_id = _dashboard_sessions.pop(sid, None)
        logger.info(f"Dashboard disconnected: sid={sid}, user_id={user_id}")

    def on_dashboard_subscribe_task(self, data):
        """Subscribe to a specific task's real-time data."""
        sid = flask_request.sid
        if sid not in _dashboard_sessions:
            emit('error', {'code': 'WS_AUTH_FAILED', 'message': '未认证'})
            return

        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'code': 'WS_BAD_REQUEST', 'message': '缺少 task_id'})
            return

        # Validate task exists
        from server.models.task import ProbeTask
        from server.extensions import db
        task = db.session.get(ProbeTask, task_id)
        if not task:
            emit('error', {'code': 'WS_INVALID_SUBSCRIBE', 'message': f'任务 {task_id} 不存在'})
            return

        room = f'task:{task_id}'
        join_room(room)
        logger.info(f"Dashboard sid={sid} subscribed to {room}")

    def on_dashboard_unsubscribe_task(self, data):
        """Unsubscribe from a task's real-time data."""
        sid = flask_request.sid
        task_id = data.get('task_id')
        if task_id:
            room = f'task:{task_id}'
            leave_room(room)
            logger.info(f"Dashboard sid={sid} unsubscribed from {room}")

    def on_dashboard_reset_mtr(self, data):
        """Reset MTR statistics: restart the task on the agent and notify dashboard."""
        sid = flask_request.sid
        if sid not in _dashboard_sessions:
            emit('error', {'code': 'WS_AUTH_FAILED', 'message': '未认证'})
            return

        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'code': 'WS_BAD_REQUEST', 'message': '缺少 task_id'})
            return

        from server.models.task import ProbeTask
        from server.extensions import db
        task = db.session.get(ProbeTask, task_id)
        if not task:
            emit('error', {'code': 'WS_INVALID_SUBSCRIBE', 'message': f'任务 {task_id} 不存在'})
            return

        # Send restart command to the agent
        from server.services.node_service import get_connection_sid
        agent_sid = get_connection_sid(task.source_node_id)
        if agent_sid:
            from datetime import datetime, timezone
            reset_time = datetime.now(timezone.utc)
            reset_time_str = reset_time.isoformat().replace('+00:00', 'Z')

            # Persist reset time to database
            task.mtr_reset_time = reset_time
            db.session.commit()

            socketio.emit('center:restart_task', {'task_id': task_id}, room=agent_sid, namespace='/agent')
            logger.info(f"Sent restart_task to agent sid={agent_sid} for task {task_id}")

            # Notify all dashboard subscribers of this task to reset their state
            room = f'task:{task_id}'
            socketio.emit('dashboard:mtr_reset', {'task_id': task_id, 'reset_time': reset_time_str}, room=room, namespace='/dashboard')
        else:
            logger.warning(f"Agent for node {task.source_node_id} not connected, cannot restart task {task_id}")


def push_task_detail(task_id, result_data):
    """Push real-time probe data to subscribers of a specific task."""
    room = f'task:{task_id}'
    socketio.emit('dashboard:task_detail', {
        'task_id': task_id,
        'result': result_data,
    }, room=room, namespace='/dashboard')


def push_node_status(node_id, node_name, status):
    """Push node status change to all dashboard clients."""
    socketio.emit('dashboard:node_status', {
        'node_id': node_id,
        'name': node_name,
        'status': status,
    }, namespace='/dashboard')


def push_alert(alert_data):
    """Push alert notification to all dashboard clients."""
    socketio.emit('dashboard:alert', alert_data, namespace='/dashboard')


def register_dashboard_handlers(socketio_instance):
    socketio_instance.on_namespace(DashboardNamespace('/dashboard'))

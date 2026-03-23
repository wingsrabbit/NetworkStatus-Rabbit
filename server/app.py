"""Flask application factory."""
import logging
import os

from flask import Flask, jsonify
from flask_jwt_extended import exceptions as jwt_exceptions

from server.config import Config
from server.extensions import db, jwt, socketio


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure data directory exists
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)

    # Initialize InfluxDB service
    from server.services.influx_service import influx_service
    try:
        influx_service.init_app(app)
    except Exception as e:
        logging.warning(f"InfluxDB initialization failed (will retry later): {e}")

    # Register blueprints
    from server.api import register_blueprints
    register_blueprints(app)

    # Register WebSocket handlers
    from server.ws import register_ws_handlers
    register_ws_handlers(socketio)

    # Create database tables
    with app.app_context():
        db.create_all()

    # Register error handlers
    _register_error_handlers(app)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # Start background tasks
    _start_background_tasks(app)

    return app


def _register_error_handlers(app):
    """Register global error handlers for unified error format."""

    @app.errorhandler(400)
    def handle_400(error):
        return jsonify({
            'error': {'code': 400, 'type': 'bad_request', 'message': str(error.description)}
        }), 400

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            'error': {'code': 404, 'type': 'not_found', 'message': '请求的资源不存在'}
        }), 404

    @app.errorhandler(405)
    def handle_405(error):
        return jsonify({
            'error': {'code': 405, 'type': 'bad_request', 'message': '不支持的请求方法'}
        }), 405

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify({
            'error': {'code': 500, 'type': 'server_error', 'message': '服务器内部错误'}
        }), 500

    @jwt.unauthorized_loader
    def handle_unauthorized(reason):
        return jsonify({
            'error': {'code': 401, 'type': 'auth_error', 'message': '未登录或登录已过期'}
        }), 401

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        return jsonify({
            'error': {'code': 401, 'type': 'auth_error', 'message': '登录已过期，请重新登录'}
        }), 401

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        return jsonify({
            'error': {'code': 401, 'type': 'auth_error', 'message': '无效的认证信息'}
        }), 401


def _start_background_tasks(app):
    """Start background tasks (heartbeat checker, snapshot pusher)."""
    import time
    from datetime import datetime, timezone

    def heartbeat_checker():
        """Check node heartbeats and update status every 10 seconds.
        Also batch-flushes last_seen to DB (BUG-B05)."""
        with app.app_context():
            while True:
                try:
                    from server.services import node_service
                    from server.models.node import Node
                    from server.ws.dashboard_handler import push_node_status

                    nodes = Node.query.filter(
                        Node.status.in_(['online', 'offline']),
                        Node.enabled == True
                    ).all()

                    now = datetime.now(timezone.utc)
                    for node in nodes:
                        is_online = node_service.is_node_online(node.id)
                        new_status = 'online' if is_online else 'offline'

                        # Batch-update last_seen for online nodes
                        if is_online:
                            node.last_seen = now

                        if node.status != new_status:
                            old_status = node.status
                            node.status = new_status
                            push_node_status(node.id, node.name, new_status)
                            logging.info(f"Node {node.name} status changed: {old_status} -> {new_status}")

                    db.session.commit()
                except Exception as e:
                    logging.error(f"Heartbeat checker error: {e}")

                socketio.sleep(10)

    def snapshot_pusher():
        """Push probe snapshots to dashboard every second with real data."""
        with app.app_context():
            while True:
                try:
                    from server.ws.agent_handler import get_latest_results
                    from server.services.alert_service import get_alert_status

                    latest = get_latest_results()
                    task_data = {}
                    for task_id, result in latest.items():
                        task_data[task_id] = {
                            'last_latency': result.get('latency'),
                            'last_packet_loss': result.get('packet_loss'),
                            'last_success': result.get('success'),
                            'status': get_alert_status(task_id),
                        }

                    snapshot = {
                        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
                        'tasks': task_data,
                    }
                    socketio.emit('dashboard:probe_snapshot', snapshot, namespace='/dashboard')
                except Exception as e:
                    logging.error(f"Snapshot pusher error: {e}")

                socketio.sleep(1)

    def sync_retry_checker():
        """Check for pending task syncs that need retry (every 10 seconds)."""
        with app.app_context():
            while True:
                try:
                    from server.services import task_service, node_service
                    retries = task_service.check_pending_syncs()
                    for node_id, config_version in retries:
                        sid = node_service.get_connection_sid(node_id)
                        if sid:
                            tasks = task_service.get_tasks_for_node(node_id)
                            socketio.emit('center:task_sync', {
                                'config_version': config_version,
                                'tasks': [t.to_agent_dict() for t in tasks]
                            }, to=sid, namespace='/agent')
                        else:
                            task_service.mark_sync_desync(node_id)
                except Exception as e:
                    logging.error(f"Sync retry checker error: {e}")

                socketio.sleep(10)

    socketio.start_background_task(heartbeat_checker)
    socketio.start_background_task(snapshot_pusher)
    socketio.start_background_task(sync_retry_checker)

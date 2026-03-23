"""Tasks management API - /api/tasks"""
from flask import Blueprint, jsonify, request

from server.extensions import db
from server.models.node import Node
from server.models.task import ProbeTask
from server.services import task_service
from server.utils.auth import admin_required, login_required
from server.utils.errors import bad_request, not_found, validation_error

tasks_bp = Blueprint('tasks', __name__)

VALID_PROTOCOLS = {'icmp', 'tcp', 'udp', 'http', 'dns'}


@tasks_bp.route('', methods=['GET'])
@login_required
def list_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    query = ProbeTask.query
    sort_col = getattr(ProbeTask, sort, ProbeTask.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [t.to_dict() for t in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'total_pages': pagination.pages
        }
    }), 200


@tasks_bp.route('', methods=['POST'])
@admin_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    # Validate required fields
    source_node_id = data.get('source_node_id')
    if not source_node_id:
        return validation_error('源节点不能为空', {'field': 'source_node_id'})

    source_node = db.session.get(Node, source_node_id)
    if not source_node:
        return not_found('源节点不存在')

    protocol = data.get('protocol', '').lower()
    if protocol not in VALID_PROTOCOLS:
        return validation_error(f'协议必须是 {", ".join(VALID_PROTOCOLS)} 之一',
                                {'field': 'protocol', 'value': protocol})

    target_type = data.get('target_type', '')
    if target_type not in ('internal', 'external'):
        return validation_error('目标类型必须是 internal 或 external', {'field': 'target_type'})

    if target_type == 'internal':
        target_node_id = data.get('target_node_id')
        if not target_node_id:
            return validation_error('内部目标节点 ID 不能为空', {'field': 'target_node_id'})
        target_node = db.session.get(Node, target_node_id)
        if not target_node:
            return not_found('目标节点不存在')
    else:
        target_address = data.get('target_address', '').strip()
        if not target_address:
            return validation_error('外部目标地址不能为空', {'field': 'target_address'})

    interval = data.get('interval', 5)
    if not isinstance(interval, int) or interval < 1 or interval > 60:
        return validation_error('探测间隔必须在 1-60 秒之间',
                                {'field': 'interval', 'value': interval, 'constraint': '1 <= interval <= 60'})

    timeout = data.get('timeout', 10)
    if not isinstance(timeout, int) or timeout < 1:
        return validation_error('超时时间必须为正整数', {'field': 'timeout'})

    task = ProbeTask(
        name=data.get('name'),
        source_node_id=source_node_id,
        target_type=target_type,
        target_node_id=data.get('target_node_id') if target_type == 'internal' else None,
        target_address=data.get('target_address') if target_type == 'external' else None,
        target_port=data.get('target_port'),
        protocol=protocol,
        interval=interval,
        timeout=timeout,
        enabled=True,
        alert_latency_threshold=data.get('alert_latency_threshold'),
        alert_loss_threshold=data.get('alert_loss_threshold'),
        alert_fail_count=data.get('alert_fail_count'),
        alert_eval_window=data.get('alert_eval_window', 5),
        alert_trigger_count=data.get('alert_trigger_count', 3),
        alert_recovery_count=data.get('alert_recovery_count', 3),
        alert_cooldown_seconds=data.get('alert_cooldown_seconds', 300),
    )
    db.session.add(task)
    db.session.flush()

    # Increment config_version for the source node
    new_version = task_service.increment_config_version(source_node_id)

    db.session.commit()

    # Notify agent via WebSocket
    _notify_agent_task_change(source_node_id, 'center_task_assign', task, new_version)

    return jsonify({'task': task.to_dict()}), 201


@tasks_bp.route('/<task_id>', methods=['PUT'])
@admin_required
def update_task(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    # Validate interval if provided
    if 'interval' in data:
        interval = data['interval']
        if not isinstance(interval, int) or interval < 1 or interval > 60:
            return validation_error('探测间隔必须在 1-60 秒之间',
                                    {'field': 'interval', 'value': interval, 'constraint': '1 <= interval <= 60'})
        task.interval = interval

    updatable_fields = [
        'name', 'timeout', 'target_port',
        'alert_latency_threshold', 'alert_loss_threshold', 'alert_fail_count',
        'alert_eval_window', 'alert_trigger_count', 'alert_recovery_count',
        'alert_cooldown_seconds'
    ]
    for field in updatable_fields:
        if field in data:
            setattr(task, field, data[field])

    new_version = task_service.increment_config_version(task.source_node_id)
    db.session.commit()

    _notify_agent_task_change(task.source_node_id, 'center_task_update', task, new_version)

    return jsonify({'task': task.to_dict()}), 200


@tasks_bp.route('/<task_id>', methods=['DELETE'])
@admin_required
def delete_task(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    source_node_id = task.source_node_id
    task_id_copy = task.id

    db.session.delete(task)
    new_version = task_service.increment_config_version(source_node_id)
    db.session.commit()

    # Notify agent
    from server.services.node_service import get_connection_sid
    from server.extensions import socketio
    sid = get_connection_sid(source_node_id)
    if sid:
        socketio.emit('center_task_remove', {
            'task_id': task_id_copy,
            'config_version': new_version
        }, to=sid, namespace='/agent')

    return jsonify({'message': '任务已删除'}), 200


@tasks_bp.route('/<task_id>/toggle', methods=['PUT'])
@admin_required
def toggle_task(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    data = request.get_json(silent=True)
    if not data or 'enabled' not in data:
        return bad_request('请求体必须包含 enabled 字段')

    task.enabled = bool(data['enabled'])
    new_version = task_service.increment_config_version(task.source_node_id)
    db.session.commit()

    _notify_agent_task_change(task.source_node_id, 'center_task_update', task, new_version)

    return jsonify({
        'task': {
            'id': task.id,
            'name': task.name,
            'enabled': task.enabled,
        }
    }), 200


def _notify_agent_task_change(node_id, event, task, config_version):
    """Notify connected agent about task changes."""
    from server.services.node_service import get_connection_sid
    from server.extensions import socketio
    sid = get_connection_sid(node_id)
    if sid:
        payload = task.to_agent_dict()
        payload['config_version'] = config_version
        if event == 'center_task_update':
            payload['changes'] = payload  # Include all current values
        socketio.emit(event, payload, to=sid, namespace='/agent')

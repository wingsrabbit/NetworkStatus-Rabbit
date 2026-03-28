"""Data query API - /api/data"""
from flask import Blueprint, jsonify, request

from server.extensions import db
from server.models.node import Node
from server.models.task import ProbeTask
from server.services.influx_service import influx_service
from server.utils.auth import login_required
from server.utils.errors import not_found

data_bp = Blueprint('data', __name__)


@data_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    from server.ws.agent_handler import get_latest_results
    from server.services.alert_service import get_alert_status

    # Optional filters
    protocol_filter = request.args.get('protocol')
    label_filter = request.args.get('label')
    status_filter = request.args.get('status')
    alert_status_filter = request.args.get('alert_status')
    search_filter = request.args.get('search')

    # Query nodes
    nodes_query = Node.query
    if status_filter:
        nodes_query = nodes_query.filter_by(status=status_filter)
    if label_filter:
        nodes_query = nodes_query.filter(
            db.or_(
                Node.label_1.ilike(f'%{label_filter}%'),
                Node.label_2.ilike(f'%{label_filter}%'),
                Node.label_3.ilike(f'%{label_filter}%'),
            )
        )
    nodes = nodes_query.order_by(Node.name.asc()).all()
    node_map = {n.id: n for n in nodes}

    # Query tasks
    tasks_query = ProbeTask.query
    if protocol_filter:
        tasks_query = tasks_query.filter_by(protocol=protocol_filter)
    if search_filter:
        matching_node_ids = [n.id for n in Node.query.filter(
            Node.name.ilike(f'%{search_filter}%')
        ).all()]
        tasks_query = tasks_query.filter(
            db.or_(
                ProbeTask.name.ilike(f'%{search_filter}%'),
                ProbeTask.target_address.ilike(f'%{search_filter}%'),
                ProbeTask.source_node_id.in_(matching_node_ids) if matching_node_ids else db.false(),
            )
        )

    tasks = tasks_query.all()

    # Get latest results and alert states
    latest_results = get_latest_results()

    # Build tasks list per spec: {nodes, tasks, summary}
    task_list = []
    alerting_count = 0
    for t in tasks:
        source = node_map.get(t.source_node_id) or db.session.get(Node, t.source_node_id)
        target_name = t.target_address
        if t.target_type == 'internal' and t.target_node_id:
            target = db.session.get(Node, t.target_node_id)
            target_name = target.name if target else t.target_node_id

        # Real latest data from in-memory cache
        latest = latest_results.get(t.id)

        # Real alert status from alert state machine
        a_status = get_alert_status(t.id)
        if a_status == 'alerting':
            alerting_count += 1

        task_list.append({
            'task_id': t.id,
            'name': t.name,
            'source_node': source.name if source else t.source_node_id,
            'target': target_name or '',
            'protocol': t.protocol,
            'enabled': t.enabled,
            'latest': latest,
            'alert_status': a_status,
        })

    # Filter by alert_status if requested
    if alert_status_filter:
        task_list = [t for t in task_list if t['alert_status'] == alert_status_filter]

    # Sort: alerting first, then by name
    task_list.sort(key=lambda t: (0 if t['alert_status'] == 'alerting' else 1, t['name'] or ''))

    online_count = sum(1 for n in nodes if n.status == 'online')
    offline_count = sum(1 for n in nodes if n.status == 'offline')

    # Build nodes list per spec
    node_list = []
    for n in nodes:
        node_list.append({
            'id': n.id,
            'name': n.name,
            'status': n.status,
            'labels': [n.label_1, n.label_2, n.label_3],
            'capabilities': n._parse_capabilities(),
            'last_seen': n.last_seen.isoformat() + 'Z' if n.last_seen else None,
        })

    return jsonify({
        'nodes': node_list,
        'tasks': task_list,
        'summary': {
            'total_nodes': len(nodes),
            'online_nodes': online_count,
            'offline_nodes': offline_count,
            'total_tasks': len(tasks),
            'alerting_tasks': alerting_count,
        }
    }), 200


@data_bp.route('/task/<task_id>', methods=['GET'])
@login_required
def task_data(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    time_range = request.args.get('range', '1h')
    data = influx_service.query_task_data(task_id, time_range)
    return jsonify({'data': data}), 200


@data_bp.route('/task/<task_id>/stats', methods=['GET'])
@login_required
def task_stats(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    time_range = request.args.get('range', '24h')
    stats = influx_service.query_task_stats(task_id, time_range)

    # Append task interval, timeout and window metadata
    from datetime import datetime, timezone, timedelta
    range_seconds = _parse_range_to_seconds(time_range)
    tail_seconds = task.timeout or 10
    now = datetime.now(timezone.utc)
    effective_end = now - timedelta(seconds=tail_seconds)
    effective_start = effective_end - timedelta(seconds=range_seconds)

    stats['interval_seconds'] = task.interval
    stats['timeout_seconds'] = task.timeout
    stats['window_start'] = effective_start.isoformat() + 'Z'
    stats['window_end'] = effective_end.isoformat() + 'Z'

    # Bucket-aware expected probes
    bucket_type = _get_bucket_type(time_range)
    stats['bucket_type'] = bucket_type
    if bucket_type == 'raw':
        stats['expected_probes'] = range_seconds // task.interval if task.interval else None
    elif bucket_type == '1m':
        stats['expected_probes'] = range_seconds // 60
    else:  # 1h
        stats['expected_probes'] = range_seconds // 3600

    return jsonify({'stats': stats}), 200


@data_bp.route('/task/<task_id>/alerts', methods=['GET'])
@login_required
def task_alert_intervals(task_id):
    """Return alert history for a task within a time range (for markArea)."""
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    time_range = request.args.get('range', '1h')
    from server.models.alert import AlertHistory
    from datetime import datetime, timezone, timedelta
    range_seconds = _parse_range_to_seconds(time_range)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=range_seconds)

    alerts = AlertHistory.query.filter(
        AlertHistory.task_id == task_id,
        AlertHistory.created_at >= cutoff
    ).order_by(AlertHistory.created_at.asc()).all()

    return jsonify({'alerts': [a.to_dict() for a in alerts]}), 200


def _parse_range_to_seconds(time_range: str) -> int:
    if time_range.endswith('m'):
        return int(time_range[:-1]) * 60
    elif time_range.endswith('h'):
        return int(time_range[:-1]) * 3600
    elif time_range.endswith('d'):
        return int(time_range[:-1]) * 86400
    return 3600


def _get_bucket_type(time_range: str) -> str:
    """Determine bucket type matching influx_service._select_bucket logic.

    v0.130: ≤1h → raw, ≤3d → 1m, >3d → 1h
    """
    seconds = _parse_range_to_seconds(time_range)
    hours = seconds / 3600
    if hours <= 1:
        return 'raw'
    elif hours <= 3 * 24:
        return '1m'
    else:
        return '1h'

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

    # Query tasks
    tasks_query = ProbeTask.query
    if protocol_filter:
        tasks_query = tasks_query.filter_by(protocol=protocol_filter)
    if search_filter:
        tasks_query = tasks_query.filter(
            db.or_(
                ProbeTask.name.ilike(f'%{search_filter}%'),
            )
        )

    # Sort: alerting tasks first, then by name
    tasks = tasks_query.order_by(ProbeTask.name.asc()).all()

    # Build response
    node_list = []
    for n in nodes:
        caps = n._parse_capabilities()
        node_list.append({
            'id': n.id,
            'name': n.name,
            'status': n.status,
            'labels': [n.label_1, n.label_2, n.label_3],
            'capabilities': caps,
            'last_seen': n.last_seen.isoformat() + 'Z' if n.last_seen else None,
        })

    task_list = []
    for t in tasks:
        source = db.session.get(Node, t.source_node_id)
        target_name = t.target_address
        if t.target_type == 'internal' and t.target_node_id:
            target = db.session.get(Node, t.target_node_id)
            target_name = target.name if target else t.target_node_id

        task_list.append({
            'task_id': t.id,
            'name': t.name,
            'source_node': source.name if source else t.source_node_id,
            'source_node_id': t.source_node_id,
            'target': target_name,
            'protocol': t.protocol,
            'enabled': t.enabled,
            'latest': None,  # Filled by real-time snapshot
            'alert_status': 'normal',  # Updated by alert engine
        })

    online_count = sum(1 for n in nodes if n.status == 'online')
    offline_count = sum(1 for n in nodes if n.status == 'offline')

    return jsonify({
        'nodes': node_list,
        'tasks': task_list,
        'summary': {
            'total_nodes': len(nodes),
            'online_nodes': online_count,
            'offline_nodes': offline_count,
            'total_tasks': len(tasks),
            'alerting_tasks': 0,  # Updated by alert engine
        }
    }), 200


@data_bp.route('/task/<task_id>', methods=['GET'])
@login_required
def task_data(task_id):
    task = db.session.get(ProbeTask, task_id)
    if not task:
        return not_found('任务不存在')

    time_range = request.args.get('range', '6h')
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
    return jsonify({'stats': stats}), 200

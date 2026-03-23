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

    # Query nodes into a lookup dict
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

    # BUG-B02: search covers task name, node name, target address
    if search_filter:
        # Get node IDs matching search
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

    tasks = tasks_query.order_by(ProbeTask.name.asc()).all()

    # Build cards for frontend
    cards = []
    for t in tasks:
        source = node_map.get(t.source_node_id) or db.session.get(Node, t.source_node_id)
        target_name = t.target_address
        if t.target_type == 'internal' and t.target_node_id:
            target = db.session.get(Node, t.target_node_id)
            target_name = target.name if target else t.target_node_id

        cards.append({
            'task_id': t.id,
            'task_name': t.name,
            'protocol': t.protocol,
            'source_node_id': t.source_node_id,
            'source_node_name': source.name if source else t.source_node_id,
            'source_node_status': source.status if source else 'offline',
            'target_address': target_name or '',
            'target_type': t.target_type,
            'target_node_id': t.target_node_id,
            'enabled': t.enabled,
            'latest': None,
            'alert_status': 'normal',
        })

    # BUG-B02: Sort alerting tasks first
    cards.sort(key=lambda c: (0 if c['alert_status'] != 'normal' else 1, c['task_name'] or ''))

    online_count = sum(1 for n in nodes if n.status == 'online')
    offline_count = sum(1 for n in nodes if n.status == 'offline')

    return jsonify({
        'cards': cards,
        'summary': {
            'total_nodes': len(nodes),
            'online_nodes': online_count,
            'offline_nodes': offline_count,
            'total_tasks': len(tasks),
            'alerting_tasks': 0,
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

"""Alerts API - /api/alerts"""
from flask import Blueprint, jsonify, request

from server.extensions import db
from server.models.alert import AlertChannel, AlertHistory
from server.utils.auth import admin_required, login_required
from server.utils.errors import bad_request, not_found, validation_error
from server.utils.webhook import send_webhook

alerts_bp = Blueprint('alerts', __name__)


# --- Channels ---

@alerts_bp.route('/channels', methods=['GET'])
@admin_required
def list_channels():
    channels = AlertChannel.query.all()
    return jsonify({'items': [c.to_dict() for c in channels]}), 200


@alerts_bp.route('/channels', methods=['POST'])
@admin_required
def create_channel():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    name = data.get('name', '').strip()
    url = data.get('url', '').strip()
    if not name:
        return validation_error('通道名称不能为空', {'field': 'name'})
    if not url:
        return validation_error('Webhook URL 不能为空', {'field': 'url'})

    channel = AlertChannel(
        name=name,
        type=data.get('type', 'webhook'),
        url=url,
        enabled=data.get('enabled', True),
    )
    db.session.add(channel)
    db.session.commit()

    return jsonify({'channel': channel.to_dict()}), 201


@alerts_bp.route('/channels/<channel_id>', methods=['PUT'])
@admin_required
def update_channel(channel_id):
    channel = db.session.get(AlertChannel, channel_id)
    if not channel:
        return not_found('告警通道不存在')

    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    for field in ['name', 'url', 'type', 'enabled']:
        if field in data:
            if field == 'enabled':
                setattr(channel, field, bool(data[field]))
            else:
                setattr(channel, field, data[field])

    db.session.commit()
    return jsonify({'channel': channel.to_dict()}), 200


@alerts_bp.route('/channels/<channel_id>', methods=['DELETE'])
@admin_required
def delete_channel(channel_id):
    channel = db.session.get(AlertChannel, channel_id)
    if not channel:
        return not_found('告警通道不存在')

    db.session.delete(channel)
    db.session.commit()
    return jsonify({'message': '通道已删除'}), 200


@alerts_bp.route('/channels/<channel_id>/test', methods=['POST'])
@admin_required
def test_channel(channel_id):
    channel = db.session.get(AlertChannel, channel_id)
    if not channel:
        return not_found('告警通道不存在')

    test_payload = {
        'event': 'test',
        'message': 'NetworkStatus-Rabbit 告警测试',
        'channel_name': channel.name,
    }
    success = send_webhook(channel.url, test_payload)
    if success:
        return jsonify({'message': '测试发送成功'}), 200
    else:
        return jsonify({'message': '测试发送失败，请检查 Webhook URL'}), 200


# --- History ---

@alerts_bp.route('/history', methods=['GET'])
@login_required
def list_history():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    task_id_filter = request.args.get('task_id')
    event_type_filter = request.args.get('event_type')

    query = AlertHistory.query
    if task_id_filter:
        query = query.filter_by(task_id=task_id_filter)
    if event_type_filter:
        query = query.filter_by(event_type=event_type_filter)

    sort_col = getattr(AlertHistory, sort, AlertHistory.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [h.to_dict() for h in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'total_pages': pagination.pages
        }
    }), 200

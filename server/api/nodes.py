"""Nodes management API - /api/nodes"""
import secrets
import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request

from server.extensions import db
from server.models.node import Node
from server.utils.auth import admin_required, login_required
from server.utils.errors import bad_request, not_found, conflict, validation_error

nodes_bp = Blueprint('nodes', __name__)


@nodes_bp.route('', methods=['GET'])
@login_required
def list_nodes():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    query = Node.query
    sort_col = getattr(Node, sort, Node.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [n.to_dict() for n in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'total_pages': pagination.pages
        }
    }), 200


@nodes_bp.route('', methods=['POST'])
@admin_required
def create_node():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    name = data.get('name', '').strip()
    if not name:
        return validation_error('节点名称不能为空', {'field': 'name'})

    # Check duplicate name
    if Node.query.filter_by(name=name).first():
        return conflict(f'节点名称 "{name}" 已存在')

    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = bcrypt.hashpw(raw_token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    node = Node(
        name=name,
        token=token_hash,
        token_plain=raw_token,
        label_1=data.get('label_1'),
        label_2=data.get('label_2'),
        label_3=data.get('label_3'),
        status='registered',
        enabled=True,
        config_version=0,
    )
    db.session.add(node)
    db.session.commit()

    # Return node data with raw token (shown only once)
    node_dict = node.to_dict()
    node_dict['token'] = raw_token
    return jsonify({'node': node_dict}), 201


@nodes_bp.route('/<node_id>', methods=['PUT'])
@admin_required
def update_node(node_id):
    node = db.session.get(Node, node_id)
    if not node:
        return not_found('节点不存在')

    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    # Partial update
    if 'name' in data:
        new_name = data['name'].strip()
        if new_name != node.name:
            existing = Node.query.filter_by(name=new_name).first()
            if existing and existing.id != node.id:
                return conflict(f'节点名称 "{new_name}" 已存在')
            node.name = new_name

    for field in ['label_1', 'label_2', 'label_3']:
        if field in data:
            setattr(node, field, data[field])

    if 'enabled' in data:
        node.enabled = bool(data['enabled'])
        if not node.enabled:
            node.status = 'disabled'
            # Disconnect the agent if connected
            from server.services.node_service import get_connection_sid, unregister_connection, clear_heartbeats
            from server.extensions import socketio
            sid = get_connection_sid(node.id)
            if sid:
                socketio.disconnect(sid, namespace='/agent')
                unregister_connection(node.id)
                clear_heartbeats(node.id)
        elif node.status == 'disabled':
            node.status = 'registered'

    db.session.commit()
    return jsonify({'node': node.to_dict()}), 200


@nodes_bp.route('/<node_id>', methods=['DELETE'])
@admin_required
def delete_node(node_id):
    node = db.session.get(Node, node_id)
    if not node:
        return not_found('节点不存在')

    # Disconnect if online
    from server.services.node_service import get_connection_sid, unregister_connection, clear_heartbeats
    from server.extensions import socketio
    sid = get_connection_sid(node.id)
    if sid:
        socketio.disconnect(sid, namespace='/agent')
        unregister_connection(node.id)
        clear_heartbeats(node.id)

    db.session.delete(node)
    db.session.commit()
    return jsonify({'message': '节点已删除'}), 200


@nodes_bp.route('/<node_id>/deploy-command', methods=['GET'])
@admin_required
def get_deploy_command(node_id):
    node = db.session.get(Node, node_id)
    if not node:
        return not_found('节点不存在')

    # Generate deploy command with actual token
    host = request.host.split(':')[0]
    agent_port = 9192  # Agent connects to dedicated agent channel port
    token = node.token_plain or '<YOUR_TOKEN>'

    command = (
        f'bash <(curl -sL http://{host}:9191/api/install-agent.sh) agent '
        f'--server {host} --port {agent_port} --node-id {node.id} --token {token}'
    )
    docker_command = (
        f'docker run -d --restart=always --name ns-agent --net=host '
        f'nsr-agent '
        f'--server {host} --port {agent_port} --node-id {node.id} --token {token}'
    )
    docker_command_with_listen = (
        f'docker run -d --restart=always --name ns-agent --net=host '
        f'nsr-agent '
        f'--server {host} --port {agent_port} --node-id {node.id} --token {token} '
        f'--listen-port 9192'
    )
    return jsonify({
        'script_command': command,
        'docker_command': docker_command,
        'docker_command_listen': docker_command_with_listen,
        'node_id': node.id,
    }), 200

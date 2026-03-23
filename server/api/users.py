"""Users management API - /api/users"""
import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from server.extensions import db
from server.models.user import User
from server.utils.auth import admin_required
from server.utils.errors import bad_request, not_found, conflict, forbidden, validation_error

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    query = User.query
    sort_col = getattr(User, sort, User.created_at)
    if order == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'items': [u.to_dict() for u in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'total_pages': pagination.pages
        }
    }), 200


@users_bp.route('', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'readonly')

    if not username:
        return validation_error('用户名不能为空', {'field': 'username'})
    if not password or len(password) < 6:
        return validation_error('密码不能为空且长度至少 6 位', {'field': 'password'})
    if role not in ('admin', 'readonly'):
        return validation_error('角色必须是 admin 或 readonly', {'field': 'role'})

    if User.query.filter_by(username=username).first():
        return conflict(f'用户名 "{username}" 已存在')

    current_user_id = get_jwt_identity()
    current_user = db.session.get(User, current_user_id)

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(
        username=username,
        password_hash=password_hash,
        role=role,
        created_by=current_user.username if current_user else 'system',
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'user': user.to_dict()}), 201


@users_bp.route('/<user_id>/role', methods=['PUT'])
@admin_required
def update_role(user_id):
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    new_role = data.get('role', '')
    if new_role not in ('admin', 'readonly'):
        return validation_error('角色必须是 admin 或 readonly', {'field': 'role'})

    target_user = db.session.get(User, user_id)
    if not target_user:
        return not_found('用户不存在')

    current_user_id = get_jwt_identity()

    # Rule 3/4: Cannot modify own role
    if target_user.id == current_user_id:
        return forbidden('不允许修改自己的角色')

    # Rule 1: Cannot demote admin via Web
    if target_user.role == 'admin' and new_role == 'readonly':
        return forbidden('不允许通过 Web 降级 admin 角色')

    # Rule 2: Cannot delete/change admin to admin (no-op is fine)
    if target_user.role == 'admin' and new_role == 'admin':
        return jsonify({'user': target_user.to_dict()}), 200

    # Rule 5: Can promote readonly to admin
    target_user.role = new_role
    db.session.commit()

    return jsonify({'user': target_user.to_dict()}), 200


@users_bp.route('/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    target_user = db.session.get(User, user_id)
    if not target_user:
        return not_found('用户不存在')

    current_user_id = get_jwt_identity()

    # Rule 3: Cannot delete self
    if target_user.id == current_user_id:
        return forbidden('不允许删除自己的账户')

    # Rule 2: Cannot delete admin via Web
    if target_user.role == 'admin':
        return forbidden('不允许通过 Web 删除 admin 用户')

    # Rule 9: Ensure at least 1 admin remains (this check covers readonly deletion, but
    # the admin check above already prevents admin deletion via Web)

    db.session.delete(target_user)
    db.session.commit()

    return jsonify({'message': '用户已删除'}), 200

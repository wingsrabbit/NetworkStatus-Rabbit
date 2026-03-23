"""Authentication API - POST /api/auth/login, /api/auth/logout, GET /api/auth/me"""
from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from server.extensions import db
from server.models.user import User
from server.utils.errors import bad_request, unauthorized, rate_limited

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return bad_request('用户名和密码不能为空')

    user = User.query.filter_by(username=username).first()
    if not user:
        return unauthorized('用户名或密码错误')

    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds())
        return rate_limited(f'账户已锁定，请 {remaining} 秒后重试')

    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        user.failed_login_count += 1
        if user.failed_login_count >= 10:
            from datetime import timedelta
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_count = 0
        db.session.commit()
        return unauthorized('用户名或密码错误')

    # Login success - reset counters
    user.failed_login_count = 0
    user.locked_until = None
    db.session.commit()

    # Create JWT and set as httpOnly cookie
    access_token = create_access_token(identity=user.id)
    resp = jsonify({'user': user.to_dict()})
    set_access_cookies(resp, access_token)
    return resp, 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    resp = jsonify({'message': '已登出'})
    unset_jwt_cookies(resp)
    return resp, 200


@auth_bp.route('/me', methods=['GET'])
def me():
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return unauthorized('用户不存在')
    return jsonify({'user': user.to_dict()}), 200

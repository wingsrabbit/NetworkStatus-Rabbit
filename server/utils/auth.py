from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from server.extensions import db
from server.models.user import User


def admin_required(fn):
    """Decorator: require admin role for the endpoint."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)
        if not user or user.role != 'admin':
            return jsonify({
                'error': {
                    'code': 403,
                    'type': 'permission_error',
                    'message': '需要管理员权限'
                }
            }), 403
        return fn(*args, **kwargs)
    return wrapper


def login_required(fn):
    """Decorator: require any authenticated user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        return fn(*args, **kwargs)
    return wrapper

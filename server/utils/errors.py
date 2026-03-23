"""Unified error response helpers per Section 14.9."""
from flask import jsonify


def error_response(code, error_type, message, details=None):
    """Create a unified error JSON response.

    REST API error format:
    { "error": { "code": int, "type": string, "message": string, "details"?: object } }
    """
    body = {
        'error': {
            'code': code,
            'type': error_type,
            'message': message
        }
    }
    if details is not None:
        body['error']['details'] = details
    return jsonify(body), code


def bad_request(message, details=None):
    return error_response(400, 'bad_request', message, details)


def unauthorized(message='未登录或登录已过期'):
    return error_response(401, 'auth_error', message)


def forbidden(message='权限不足'):
    return error_response(403, 'permission_error', message)


def not_found(message='资源不存在'):
    return error_response(404, 'not_found', message)


def conflict(message):
    return error_response(409, 'conflict', message)


def validation_error(message, details=None):
    return error_response(422, 'validation_error', message, details)


def rate_limited(message='请求过于频繁，请稍后重试'):
    return error_response(429, 'rate_limited', message)


def server_error(message='服务器内部错误'):
    return error_response(500, 'server_error', message)

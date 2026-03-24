"""System settings API - /api/settings"""
import json

from flask import Blueprint, jsonify, request

from server.extensions import db
from server.models.alert import Setting
from server.utils.auth import admin_required
from server.utils.errors import bad_request

settings_bp = Blueprint('settings', __name__)

# Default settings
DEFAULT_SETTINGS = {
    'data_retention_raw_days': 3,
    'data_retention_1m_days': 7,
    'data_retention_1h_days': 30,
    'default_probe_interval': 5,
    'default_probe_timeout': 10,
    'global_alert_cooldown': 300,
    'site_title': 'NetworkStatus-Rabbit',
    'site_subtitle': '网络质量监控平台',
}


def _get_all_settings():
    """Get all settings merged with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    for s in Setting.query.all():
        try:
            settings[s.key] = json.loads(s.value) if s.value else None
        except (json.JSONDecodeError, TypeError):
            settings[s.key] = s.value
    return settings


@settings_bp.route('/public', methods=['GET'])
def get_public_settings():
    """Return site_title/site_subtitle without auth (for all visitors)."""
    settings = _get_all_settings()
    return jsonify({
        'site_title': settings.get('site_title', 'NetworkStatus-Rabbit'),
        'site_subtitle': settings.get('site_subtitle', '网络质量监控平台'),
    }), 200


@settings_bp.route('', methods=['GET'])
@admin_required
def get_settings():
    return jsonify({'settings': _get_all_settings()}), 200


@settings_bp.route('', methods=['PUT'])
@admin_required
def update_settings():
    data = request.get_json(silent=True)
    if not data:
        return bad_request('请求体必须是 JSON 格式')

    for key, value in data.items():
        setting = Setting.query.get(key)
        if setting:
            setting.value = json.dumps(value)
        else:
            setting = Setting(key=key, value=json.dumps(value))
            db.session.add(setting)

    db.session.commit()
    return jsonify({'settings': _get_all_settings()}), 200

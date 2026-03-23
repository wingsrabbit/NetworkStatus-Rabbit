import uuid
from datetime import datetime, timezone

from server.extensions import db


class AlertChannel(db.Model):
    __tablename__ = 'alert_channels'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(20), nullable=False, default='webhook')
    url = db.Column(db.String(500), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'url': self.url,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class AlertHistory(db.Model):
    __tablename__ = 'alert_history'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = db.Column(db.String(36), db.ForeignKey('probe_tasks.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # alert / recovery
    metric = db.Column(db.String(30), nullable=False)  # latency / packet_loss / continuous_fail
    actual_value = db.Column(db.Float, nullable=False)
    threshold = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, nullable=True)
    alert_started_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    notified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    task = db.relationship('ProbeTask', backref='alert_history')

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'task_name': self.task.name if self.task else None,
            'event_type': self.event_type,
            'metric': self.metric,
            'actual_value': self.actual_value,
            'threshold': self.threshold,
            'message': self.message,
            'alert_started_at': self.alert_started_at.isoformat() + 'Z' if self.alert_started_at else None,
            'duration_seconds': self.duration_seconds,
            'notified': self.notified,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class Setting(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)  # JSON serialized

    def to_dict(self):
        import json
        try:
            parsed = json.loads(self.value) if self.value else None
        except (json.JSONDecodeError, TypeError):
            parsed = self.value
        return {self.key: parsed}

import uuid
from datetime import datetime, timezone

from server.extensions import db


class ProbeTask(db.Model):
    __tablename__ = 'probe_tasks'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(200), nullable=True)
    source_node_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)  # internal / external
    target_node_id = db.Column(db.String(36), db.ForeignKey('nodes.id'), nullable=True)
    target_address = db.Column(db.String(255), nullable=True)
    target_port = db.Column(db.Integer, nullable=True)
    protocol = db.Column(db.String(10), nullable=False)  # icmp/tcp/udp/http/dns
    interval = db.Column(db.Integer, nullable=False, default=5)
    timeout = db.Column(db.Integer, nullable=False, default=10)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Alert parameters
    alert_latency_threshold = db.Column(db.Float, nullable=True)
    alert_loss_threshold = db.Column(db.Float, nullable=True)
    alert_fail_count = db.Column(db.Integer, nullable=True)
    alert_eval_window = db.Column(db.Integer, nullable=False, default=5)
    alert_trigger_count = db.Column(db.Integer, nullable=False, default=3)
    alert_recovery_count = db.Column(db.Integer, nullable=False, default=3)
    alert_cooldown_seconds = db.Column(db.Integer, nullable=False, default=300)

    # Relationships
    source_node = db.relationship('Node', foreign_keys=[source_node_id], backref='source_tasks')
    target_node = db.relationship('Node', foreign_keys=[target_node_id])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_node_id': self.source_node_id,
            'target_type': self.target_type,
            'target_node_id': self.target_node_id,
            'target_address': self.target_address,
            'target_port': self.target_port,
            'protocol': self.protocol,
            'interval': self.interval,
            'timeout': self.timeout,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'alert_latency_threshold': self.alert_latency_threshold,
            'alert_loss_threshold': self.alert_loss_threshold,
            'alert_fail_count': self.alert_fail_count,
            'alert_eval_window': self.alert_eval_window,
            'alert_trigger_count': self.alert_trigger_count,
            'alert_recovery_count': self.alert_recovery_count,
            'alert_cooldown_seconds': self.alert_cooldown_seconds,
        }

    def to_agent_dict(self):
        """Format for sending to agent via WebSocket."""
        target_addr = self.target_address
        if self.target_type == 'internal' and self.target_node:
            target_addr = self.target_node.public_ip or self.target_node.private_ip or self.target_node.name
        return {
            'task_id': self.id,
            'target_type': self.target_type,
            'target_address': target_addr,
            'target_port': self.target_port,
            'protocol': self.protocol,
            'interval': self.interval,
            'timeout': self.timeout,
            'enabled': self.enabled,
        }

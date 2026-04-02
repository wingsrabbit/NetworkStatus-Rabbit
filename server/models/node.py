import uuid
from datetime import datetime, timezone

from server.extensions import db


class Node(db.Model):
    __tablename__ = 'nodes'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False, unique=True)
    token = db.Column(db.String(256), nullable=False)  # bcrypt hash
    token_plain = db.Column(db.String(256), nullable=True)  # plaintext for deploy commands
    label_1 = db.Column(db.String(80), nullable=True)
    label_2 = db.Column(db.String(80), nullable=True)
    label_3 = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='registered')
    last_seen = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    config_version = db.Column(db.Integer, nullable=False, default=0)
    capabilities = db.Column(db.Text, nullable=True)  # JSON
    agent_version = db.Column(db.String(20), nullable=True)
    public_ip = db.Column(db.String(45), nullable=True)
    private_ip = db.Column(db.String(45), nullable=True)

    def to_dict(self, include_token=False):
        d = {
            'id': self.id,
            'name': self.name,
            'label_1': self.label_1,
            'label_2': self.label_2,
            'label_3': self.label_3,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() + 'Z' if self.last_seen else None,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'enabled': self.enabled,
            'config_version': self.config_version,
            'capabilities': self._parse_capabilities(),
            'agent_version': self.agent_version,
            'public_ip': self.public_ip,
            'private_ip': self.private_ip,
        }
        if include_token:
            # Only used when creating node - raw token is passed separately
            pass
        return d

    def _parse_capabilities(self):
        if self.capabilities:
            import json
            try:
                return json.loads(self.capabilities)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

#!/bin/bash
set -e

echo "=== NetworkStatus-Rabbit Center Starting ==="

# Copy built frontend to shared volume (for nginx)
if [ -d /app/web/dist-build ]; then
    echo "Deploying frontend to shared volume..."
    rm -rf /app/web/dist/*
    cp -r /app/web/dist-build/* /app/web/dist/
fi

# Wait for InfluxDB
echo "Waiting for InfluxDB..."
python scripts/setup-influxdb.py

# Create default admin user if not exists
python -c "
from manage import get_app
app = get_app()
with app.app_context():
    from server.extensions import db
    from server.models.user import User
    db.create_all()
    if not User.query.first():
        import bcrypt
        pw = bcrypt.hashpw(b'admin123456', bcrypt.gensalt()).decode()
        u = User(username='admin', password_hash=pw, role='admin')
        db.session.add(u)
        db.session.commit()
        print('Created default admin user: admin / admin123456')
    else:
        print('Admin user already exists, skipping')
"

echo "Starting center server..."
exec python -c "
from server.app import create_app
from server.extensions import socketio
app = create_app()
socketio.run(app, host='0.0.0.0', port=5000)
"

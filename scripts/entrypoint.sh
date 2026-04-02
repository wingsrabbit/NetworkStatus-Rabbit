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
    # v0.133 migration: add token_plain column to nodes if missing
    import sqlite3, os
    db_path = os.path.join(app.config['DATA_DIR'], 'networkstatus.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute('PRAGMA table_info(nodes)').fetchall()]
        if 'token_plain' not in cols:
            conn.execute('ALTER TABLE nodes ADD COLUMN token_plain VARCHAR(256)')
            conn.commit()
            print('Migrated: added token_plain column to nodes table')
        # v0.133 migration: expand protocol column width if needed
        cols_tasks = [row for row in conn.execute('PRAGMA table_info(probe_tasks)').fetchall()]
        conn.close()
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

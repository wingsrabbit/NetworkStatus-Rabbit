#!/bin/bash
# Install and start NetworkStatus-Rabbit Agent
set -e

SERVER="$1"
PORT="$2"
NODE_ID="$3"
TOKEN="$4"

INSTALL_DIR="/opt/networkstatus-agent"
DATA_DIR="/var/lib/networkstatus-agent"

echo "=== Installing system dependencies ==="
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv iputils-ping curl dnsutils netcat-openbsd git >/dev/null 2>&1

echo "=== Cloning repository ==="
rm -rf "$INSTALL_DIR"
git clone --depth 1 https://github.com/wingsrabbit/NetworkStatus-Rabbit.git "$INSTALL_DIR"

echo "=== Setting up Python venv ==="
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements-agent.txt"

mkdir -p "$DATA_DIR"

echo "=== Creating systemd service ==="
cat > /etc/systemd/system/networkstatus-agent.service << EOF
[Unit]
Description=NetworkStatus-Rabbit Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/venv/bin/python -m agent.main --server $SERVER --port $PORT --node-id $NODE_ID --token $TOKEN --data-dir $DATA_DIR
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable networkstatus-agent
systemctl start networkstatus-agent

echo "=== Agent started ==="
sleep 2
systemctl status networkstatus-agent --no-pager || true

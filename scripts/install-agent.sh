#!/usr/bin/env bash
# NetworkStatus-Rabbit Agent Installation Script
# Usage: curl -sSL http://<center>/install-agent.sh | bash -s -- --server <host> --port <port> --node-id <id> --token <token>

set -euo pipefail

SERVER=""
PORT="9191"
NODE_ID=""
TOKEN=""
INSTALL_DIR="/opt/networkstatus-agent"
DATA_DIR="/var/lib/networkstatus-agent"
SERVICE_NAME="networkstatus-agent"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --server) SERVER="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --node-id) NODE_ID="$2"; shift 2 ;;
        --token) TOKEN="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$SERVER" || -z "$NODE_ID" || -z "$TOKEN" ]]; then
    echo "Usage: install-agent.sh --server <host> --port <port> --node-id <id> --token <token>"
    exit 1
fi

echo "=== NetworkStatus-Rabbit Agent Installer ==="
echo "Server: ${SERVER}:${PORT}"
echo "Node ID: ${NODE_ID}"
echo "Install dir: ${INSTALL_DIR}"

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.12+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: ${PYTHON_VERSION}"

# Install system dependencies
echo "Installing system dependencies..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq iputils-ping curl dnsutils netcat-openbsd python3-pip python3-venv >/dev/null
elif command -v yum &>/dev/null; then
    sudo yum install -y -q iputils curl bind-utils nmap-ncat python3-pip >/dev/null
elif command -v apk &>/dev/null; then
    sudo apk add --quiet iputils curl bind-tools netcat-openbsd py3-pip >/dev/null
else
    echo "WARNING: Could not detect package manager. Please install: ping, curl, nslookup, nc manually."
fi

# Create directories
echo "Creating directories..."
sudo mkdir -p "${INSTALL_DIR}"
sudo mkdir -p "${DATA_DIR}"

# Create venv
echo "Setting up Python virtual environment..."
python3 -m venv "${INSTALL_DIR}/venv"
source "${INSTALL_DIR}/venv/bin/activate"

# Install Python requirements
echo "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet python-socketio[client] psutil

# Download agent code from center server
echo "Downloading agent code from center..."
AGENT_URL="http://${SERVER}:${PORT}/api/agent-package.tar.gz"
curl -fsSL "${AGENT_URL}" -o /tmp/agent-package.tar.gz
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download agent package from ${AGENT_URL}"
    exit 1
fi
echo "Extracting agent code..."
tar -xzf /tmp/agent-package.tar.gz -C "${INSTALL_DIR}/"
rm -f /tmp/agent-package.tar.gz

# Install Python requirements if requirements file exists
if [ -f "${INSTALL_DIR}/requirements-agent.txt" ]; then
    pip install --quiet -r "${INSTALL_DIR}/requirements-agent.txt"
fi

# Create startup script
cat > "${INSTALL_DIR}/run.sh" << EOFRUN
#!/usr/bin/env bash
cd "${INSTALL_DIR}"
source venv/bin/activate
exec python3 -m agent.main \\
    --server "${SERVER}" \\
    --port "${PORT}" \\
    --node-id "${NODE_ID}" \\
    --token "${TOKEN}" \\
    --data-dir "${DATA_DIR}"
EOFRUN
chmod +x "${INSTALL_DIR}/run.sh"

# Create systemd service
if command -v systemctl &>/dev/null; then
    echo "Creating systemd service..."
    cat > "/tmp/${SERVICE_NAME}.service" << EOFSVC
[Unit]
Description=NetworkStatus-Rabbit Agent
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/run.sh
Restart=always
RestartSec=5
User=root
WorkingDirectory=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
EOFSVC
    sudo mv "/tmp/${SERVICE_NAME}.service" "/etc/systemd/system/${SERVICE_NAME}.service"
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    echo "Service installed. Start with: sudo systemctl start ${SERVICE_NAME}"
else
    echo "systemd not found. Run agent manually: ${INSTALL_DIR}/run.sh"
fi

echo ""
echo "=== Installation Complete ==="
echo "Agent install dir: ${INSTALL_DIR}"
echo "Agent data dir: ${DATA_DIR}"
echo ""
echo "Start: sudo systemctl start ${SERVICE_NAME}"
echo "Status: sudo systemctl status ${SERVICE_NAME}"
echo "Logs: sudo journalctl -u ${SERVICE_NAME} -f"

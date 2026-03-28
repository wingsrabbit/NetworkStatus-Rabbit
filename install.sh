#!/bin/bash
set -e

# ============================================================
# NetworkStatus-Rabbit 一键安装脚本
# 用法:
#   服务端:  bash <(curl -sL https://raw.githubusercontent.com/wingsrabbit/NetworkStatus-Rabbit/NetworkStatus-Rabbit-NG/install.sh)
#   Agent:   bash <(curl -sL https://raw.githubusercontent.com/wingsrabbit/NetworkStatus-Rabbit/NetworkStatus-Rabbit-NG/install.sh) agent --server <IP> --port 9192 --node-id <ID> --token <TOKEN>
# ============================================================

REPO_URL="https://github.com/wingsrabbit/NetworkStatus-Rabbit.git"
BRANCH="NetworkStatus-Rabbit-NG"
INSTALL_DIR="/opt/NetworkStatus-Rabbit"
AGENT_INSTALL_DIR="/opt/networkstatus-agent"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---- Docker installation ----
install_docker() {
    if command -v docker &>/dev/null; then
        info "Docker 已安装: $(docker --version)"
        return
    fi
    info "正在安装 Docker..."
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    info "Docker 安装完成"
}

# ---- Generate random string ----
rand_str() {
    head -c "$1" /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c "$1"
}

# ============================================================
# Agent mode
# ============================================================
install_agent() {
    shift  # remove "agent"
    info "=== NetworkStatus-Rabbit Agent 安装 ==="
    install_docker

    # Parse agent args
    local SERVER="" PORT="9192" NODE_ID="" TOKEN="" LISTEN_PORT=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --server)    SERVER="$2"; shift 2 ;;
            --server=*)  SERVER="${1#*=}"; shift ;;
            --port)      PORT="$2"; shift 2 ;;
            --port=*)    PORT="${1#*=}"; shift ;;
            --node-id)   NODE_ID="$2"; shift 2 ;;
            --node-id=*) NODE_ID="${1#*=}"; shift ;;
            --token)     TOKEN="$2"; shift 2 ;;
            --token=*)   TOKEN="${1#*=}"; shift ;;
            --listen-port)   LISTEN_PORT="$2"; shift 2 ;;
            --listen-port=*) LISTEN_PORT="${1#*=}"; shift ;;
            *) shift ;;
        esac
    done

    [[ -z "$SERVER" ]] && error "缺少 --server 参数"
    [[ -z "$NODE_ID" ]] && error "缺少 --node-id 参数"
    [[ -z "$TOKEN" ]]   && error "缺少 --token 参数"

    # Clone or pull
    if [ -d "$AGENT_INSTALL_DIR/.git" ]; then
        info "更新代码..."
        cd "$AGENT_INSTALL_DIR" && git pull origin "$BRANCH"
    else
        info "克隆代码..."
        git clone -b "$BRANCH" "$REPO_URL" "$AGENT_INSTALL_DIR"
    fi
    cd "$AGENT_INSTALL_DIR"

    # Build agent image
    info "构建 Agent 镜像..."
    docker build -t nsr-agent -f Dockerfile.agent .

    # Stop old container
    docker rm -f nsr-agent 2>/dev/null || true

    # Build run command
    local DOCKER_CMD="docker run -d --restart=always --name nsr-agent --net=host"
    DOCKER_CMD+=" nsr-agent --server $SERVER --port $PORT --node-id $NODE_ID --token $TOKEN"
    if [[ -n "$LISTEN_PORT" ]]; then
        DOCKER_CMD+=" --listen-port $LISTEN_PORT"
    fi

    info "启动 Agent..."
    eval "$DOCKER_CMD"

    echo ""
    info "✅ Agent 安装完成！"
    info "容器名: nsr-agent"
    info "查看日志: docker logs -f nsr-agent"
}

# ============================================================
# Server (Center) mode
# ============================================================
install_server() {
    info "=== NetworkStatus-Rabbit 服务端安装 ==="
    install_docker

    # Clone or pull
    if [ -d "$INSTALL_DIR/.git" ]; then
        info "更新代码..."
        cd "$INSTALL_DIR" && git pull origin "$BRANCH"
    else
        info "克隆代码..."
        git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    fi
    cd "$INSTALL_DIR"

    # Generate .env if not exists
    if [ ! -f .env ]; then
        info "生成 .env 配置..."
        cat > .env <<EOF
SECRET_KEY=$(rand_str 32)
INFLUXDB_TOKEN=$(rand_str 64)
INFLUXDB_PASSWORD=$(rand_str 24)
EOF
        info ".env 已生成（密钥已自动随机生成）"
    else
        info ".env 已存在，跳过生成"
    fi

    # Build and start
    info "构建并启动服务（首次需要几分钟）..."
    docker compose up -d --build

    # Wait for backend readiness
    info "等待服务就绪..."
    local retries=0
    while ! curl -sf http://localhost:9191/api/auth/login -o /dev/null 2>/dev/null; do
        retries=$((retries + 1))
        if [ $retries -gt 30 ]; then
            warn "等待超时，请检查: docker compose logs"
            break
        fi
        sleep 2
    done

    local IP
    IP=$(curl -sf https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')

    echo ""
    echo "========================================"
    info "✅ 安装完成！"
    echo "========================================"
    echo ""
    info "🌐 监控面板:  http://${IP}:9191"
    info "🔑 默认账号:  admin / admin123456"
    info "📡 Agent 端口: ${IP}:9192"
    echo ""
    info "⚠️  请立即登录后台修改默认密码！"
    echo ""
    info "常用命令:"
    info "  查看日志:  cd $INSTALL_DIR && docker compose logs -f"
    info "  停止服务:  cd $INSTALL_DIR && docker compose down"
    info "  更新服务:  cd $INSTALL_DIR && bash update.sh"
    echo ""
}

# ---- Entry ----
if [[ "${1:-}" == "agent" ]]; then
    install_agent "$@"
else
    install_server "$@"
fi

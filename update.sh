#!/bin/bash
set -e

# ============================================================
# NetworkStatus-Rabbit 热更新脚本
# 用法: bash update.sh [container_name]
#   默认容器名: ns-center
# ============================================================

CONTAINER="${1:-ns-center}"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

cd "$INSTALL_DIR"

# Check container
docker inspect "$CONTAINER" &>/dev/null || error "容器 $CONTAINER 不存在，请先安装"

OLD_VERSION=$(docker exec "$CONTAINER" python -c "from version import APP_VERSION; print(APP_VERSION)" 2>/dev/null || echo "unknown")
info "当前版本: $OLD_VERSION"

# Pull latest code
info "拉取最新代码..."
git pull

NEW_VERSION=$(python3 -c "exec(open('version.py').read()); print(APP_VERSION)" 2>/dev/null || cat version.py | grep APP_VERSION | cut -d"'" -f2)
info "最新版本: $NEW_VERSION"

# Hot-copy backend files into container
info "热更新后端代码..."
docker cp server/. "$CONTAINER":/app/server/
docker cp scripts/. "$CONTAINER":/app/scripts/
docker cp manage.py "$CONTAINER":/app/manage.py
docker cp version.py "$CONTAINER":/app/version.py

# Check if frontend needs rebuild
FRONTEND_CHANGED=$(git diff HEAD~1 --name-only 2>/dev/null | grep "^web/" | head -1 || true)

if [ -n "$FRONTEND_CHANGED" ]; then
    warn "检测到前端文件变更，需要重新构建镜像..."
    docker compose up -d --build backend
    info "前端已重建并部署"
else
    info "重启容器应用更新..."
    docker restart "$CONTAINER"
fi

# Wait for readiness
sleep 3
RUNNING=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo "false")
if [ "$RUNNING" = "true" ]; then
    info "✅ 更新完成！$OLD_VERSION → $NEW_VERSION"
else
    error "容器未能正常启动，请检查: docker logs $CONTAINER"
fi

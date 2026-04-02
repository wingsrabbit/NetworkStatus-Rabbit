# NetworkStatus-Rabbit 🐇

分布式多节点网络质量监控平台，支持 ICMP / TCP / UDP / HTTP / DNS / MTR 六种协议探测，实时仪表盘 + 历史图表 + 告警通知。

![version](https://img.shields.io/badge/version-v0.133-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 目录

- [功能特性](#功能特性)
- [快速开始 — 服务端](#快速开始--服务端)
- [快速开始 — Agent](#快速开始--agent)
- [更新与维护](#更新与维护)
- [后台管理](#后台管理)
- [端口说明](#端口说明)
- [数据持久化](#数据持久化)
- [CLI 命令](#cli-命令)
- [非 Docker 部署](#非-docker-部署)
- [技术栈](#技术栈)
- [架构概览](#架构概览)

---

## 功能特性

| 类别 | 特性 |
|------|------|
| 探测协议 | ICMP（延迟/丢包/抖动）、TCP（连接延迟/抖动）、UDP（延迟/丢包/抖动）、HTTP（DNS/TCP/TLS/TTFB 分阶段计时 + 状态码）、DNS（解析时间 + IP 变更追踪）、MTR（ICMP/TCP/UDP 三种模式，逐跳路由追踪 + 实时刷新） |
| 实时监控 | WebSocket 推送，仪表盘卡片/列表双视图切换，分页（10/20/50），首字母排序 |
| 历史数据 | ECharts 时序图表，30分钟 ~ 30天多粒度，三级数据降采样（raw → 1m → 1h） |
| 告警引擎 | 窗口评估 + 状态机，触发/恢复/冷却，Webhook 通知（企业微信、Slack 等） |
| 节点管理 | Web 后台增删改节点，自动生成 Agent 部署命令 |
| 权限模型 | admin / readonly 角色 |
| 主题 | 明/暗主题一键切换 |
| 部署 | Docker 多阶段构建，一键安装，支持热更新 |

---

## 快速开始 — 服务端

在你的**主控服务器**上执行一行命令即可完成安装：

```bash
bash <(curl -sL https://raw.githubusercontent.com/wingsrabbit/NetworkStatus-Rabbit/NetworkStatus-Rabbit-NG/install.sh)
```

安装脚本会自动完成：
1. 检测并安装 Docker（如未安装）
2. 克隆代码到 `/opt/NetworkStatus-Rabbit`
3. 自动生成随机密钥（`.env` 文件）
4. 构建镜像并启动所有服务
5. 初始化数据库和默认管理员

启动后：
- 🌐 监控面板：`http://你的IP:9191`
- 🔑 默认账号：`admin` / `admin123456`

> ⚠️ **请立即登录后台修改默认密码！**

### 手动安装（可选）

如果你不想用一键脚本，也可以手动安装：

```bash
git clone -b NetworkStatus-Rabbit-NG https://github.com/wingsrabbit/NetworkStatus-Rabbit.git
cd NetworkStatus-Rabbit

# 生成配置文件（自动生成随机密钥）
cat > .env <<EOF
SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)
INFLUXDB_TOKEN=$(head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)
INFLUXDB_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 24)
EOF

# 构建并启动
docker compose up -d --build
```

---

## 快速开始 — Agent

Agent 部署在每台**被监控节点**上，执行探测任务并将结果上报给服务端。

### 方式一：一键安装

在后台管理「节点管理」中添加节点后，系统会生成部署命令。在目标机器上执行：

```bash
bash <(curl -sL https://raw.githubusercontent.com/wingsrabbit/NetworkStatus-Rabbit/NetworkStatus-Rabbit-NG/install.sh) agent \
  --server 服务端IP \
  --port 9192 \
  --node-id <节点ID> \
  --token <节点Token>
```

将参数替换为后台管理中生成的实际值。

### 方式二：Docker 手动部署

```bash
git clone -b NetworkStatus-Rabbit-NG https://github.com/wingsrabbit/NetworkStatus-Rabbit.git
cd NetworkStatus-Rabbit
docker build -t nsr-agent -f Dockerfile.agent .

docker run -d --restart=always --name nsr-agent --net=host \
  nsr-agent \
  --server 服务端IP \
  --port 9192 \
  --node-id <节点ID> \
  --token <节点Token>
```

> Agent 和服务端使用不同的 Dockerfile，Agent 镜像更轻量。

### 方式三：直接运行 Python（开发/调试用）

```bash
pip install -r requirements-agent.txt
python -m agent.main \
  --server 服务端IP \
  --port 9192 \
  --node-id <节点ID> \
  --token <节点Token>
```

---

## 更新与维护

### 热更新（推荐，仅后端改动时）

```bash
cd /opt/NetworkStatus-Rabbit
bash update.sh
```

脚本会自动拉取最新代码，将后端文件热拷贝到容器内并重启，**无需重建镜像**。

> **注意：** 如果涉及前端改动，脚本会自动检测并触发完整重建。

### 完整重建（涉及前端或 Dockerfile 改动时）

```bash
cd /opt/NetworkStatus-Rabbit
git pull
docker compose up -d --build
```

> `data/` 目录中的配置和数据会保留，无需重新设置。

### Agent 更新

```bash
cd /opt/networkstatus-agent
git pull
docker build -t nsr-agent -f Dockerfile.agent .
docker rm -f nsr-agent
# 重新运行启动命令
```

---

## 后台管理

登录 `http://你的IP:9191` 后可访问管理功能：

| 功能 | 说明 |
|------|------|
| 节点管理 | 增删改查，一键生成 Agent 部署命令 |
| 任务管理 | 创建探测任务，配置协议/目标/间隔/超时 |
| 告警通道 | Webhook 通知（企业微信、Slack、自定义 URL） |
| 告警历史 | 查看告警触发/恢复事件日志 |
| 用户管理 | admin / readonly 角色管理 |
| 系统设置 | 全局参数配置 |
| 深色模式 | 一键切换明/暗主题 |

### 仪表盘功能

- **卡片/列表视图切换**：点击右上角按钮在网格卡片和横向列表间切换
- **分页显示**：支持 10 / 20 / 50 条每页
- **搜索过滤**：按任务名、目标地址、节点名搜索
- **协议过滤**：下拉筛选特定协议
- **首字母排序**：任务默认按名称排序

---

## 端口说明

| 端口 | 用途 | 必需 |
|------|------|------|
| 9191 | Web 监控页 + 后台管理 + REST API（HTTP） | ✅ |
| 9192 | Agent 数据通道（WebSocket） | ✅ |

> InfluxDB 仅在 Docker 内部网络中使用，**不对外暴露端口**。

可通过环境变量自定义端口：
```bash
NSR_WEB_PORT=8080 NSR_AGENT_PORT=8081 docker compose up -d
```

---

## 数据持久化

所有持久化数据通过 Docker Volume 挂载：

```
data/                    # SQLite 数据库（用户、节点、任务配置）
influxdb_data (volume)   # InfluxDB 时序数据（自动降采样：raw 3天 → 1m聚合 7天 → 1h聚合 30天）
frontend_dist (volume)   # 前端编译文件（nginx 共享）
```

---

## CLI 命令

```bash
# 创建管理员
docker exec -it ns-center python manage.py create-admin

# 重置用户密码
docker exec -it ns-center python manage.py reset-password

# 删除管理员（至少保留一个）
docker exec -it ns-center python manage.py remove-admin
```

---

## 非 Docker 部署

<details>
<summary>点击展开（不推荐，建议使用 Docker）</summary>

### 前置要求

- Python 3.12+
- Node.js 18+
- InfluxDB 2.7

### 服务端

```bash
pip install -r requirements.txt

# 构建前端
cd web && npm install && npm run build && cd ..

# 设置环境变量
export INFLUXDB_URL=http://localhost:8086
export INFLUXDB_TOKEN=your-token
export INFLUXDB_ORG=networkstatus
export SECRET_KEY=your-secret-key

# 初始化数据库
python scripts/setup-influxdb.py
python manage.py create-admin

# 启动
python -c "
from server.app import create_app
from server.extensions import socketio
app = create_app()
socketio.run(app, host='0.0.0.0', port=5000)
"
```

### Agent

```bash
pip install -r requirements-agent.txt
python -m agent.main --server <IP> --port 9192 --node-id <ID> --token <TOKEN>
```

</details>

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 + Flask + Flask-SocketIO |
| 前端 | Vue 3 + TypeScript + Naive UI + ECharts |
| 数据库 | InfluxDB 2.7（时序数据）+ SQLite（配置数据） |
| 通信 | Socket.IO（Agent ↔ Center，Dashboard ↔ Center） |
| 容器 | Docker 多阶段构建（node:20 + python:3.12-slim） |
| 代理 | Nginx（前端静态 + API/WS 反向代理） |

---

## 架构概览

```
                        ┌──────────────────────┐
    浏览器 ◄──9191──►   │     Nginx (静态+代理)  │
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐     ┌─────────────┐
    Agent ◄──9192──►    │   Center (Flask+WS)   │◄──►│  InfluxDB   │
                        │   REST API + SocketIO │    │  (内部网络)  │
                        └──────────────────────┘     └─────────────┘
                                   ▲
                     ┌─────────────┼─────────────┐
                     ▼             ▼             ▼
                 ┌───────┐    ┌───────┐    ┌───────┐
                 │Agent 1│    │Agent 2│    │Agent N│
                 │ ICMP  │    │ HTTP  │    │ DNS   │
                 │ TCP   │    │ TCP   │    │ ICMP  │
                 │ UDP   │    │ UDP   │    │  ...  │
                 └───────┘    └───────┘    └───────┘
```

## 支持的探测协议

| 协议 | 探测指标 | 图表 |
|------|---------|------|
| ICMP | 延迟、丢包率、抖动 | 延迟曲线 + 丢包散点 + 抖动虚线 |
| TCP  | 连接延迟、抖动 | 延迟曲线 + 失败散点 + 抖动虚线 |
| UDP  | 延迟、丢包率、抖动 | 延迟曲线 + 丢包散点 + 抖动虚线 |
| HTTP | DNS/TCP/TLS/TTFB 分阶段计时、状态码 | 总时间曲线 + 阶段堆叠面积图 + 状态码散点 |
| DNS  | 解析时间、解析 IP | 解析时间曲线 + 失败散点 + IP 变更表 |

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.12, Flask 3.x, Flask-SocketIO 5.x |
| 前端 | Vue 3.4, TypeScript, Naive UI, ECharts 5.5 |
| 时序数据库 | InfluxDB 2.7 |
| 配置数据库 | SQLite |
| 反向代理 | Nginx |
| 容器化 | Docker Compose |

## License

MIT

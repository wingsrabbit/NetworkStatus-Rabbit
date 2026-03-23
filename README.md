# NetworkStatus-Rabbit 🐇

**网络质量监控平台** — 分布式多节点网络探测与实时可视化系统。

## 架构概览

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   Frontend  │◄─────►│   Center Server  │◄─────►│  InfluxDB   │
│  Vue 3 SPA  │  WS   │  Flask+SocketIO  │       │   2.7 TSB   │
└─────────────┘       └────────┬─────────┘       └─────────────┘
                               │ WS (/agent)
                     ┌─────────┼─────────┐
                     ▼         ▼         ▼
                 ┌───────┐ ┌───────┐ ┌───────┐
                 │Agent 1│ │Agent 2│ │Agent N│
                 └───────┘ └───────┘ └───────┘
```

- **Center (Server)**: Flask + Flask-SocketIO，承载 REST API、WebSocket 处理、告警引擎
- **Agent**: 部署于多个被测节点，执行 ICMP/TCP/UDP/HTTP/DNS 探测，结果实时上报
- **Frontend**: Vue 3 + Naive UI + ECharts，仪表盘实时刷新
- **InfluxDB 2.7**: 三级 Bucket（raw 3d / agg_1m 7d / agg_1h 30d）自动降采样

## 支持的探测协议

| 协议 | 指标 |
|------|------|
| ICMP | latency, packet_loss, jitter |
| TCP | latency (connect time) |
| UDP | latency |
| HTTP | dns_time, tcp_time, tls_time, ttfb, total_time, status_code |
| DNS | latency, resolved_ip |

## 快速启动

### 前置要求

- Docker + Docker Compose
- Node.js 18+ (前端构建)

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 设置 SECRET_KEY、INFLUXDB 相关参数
```

### 2. 构建前端

```bash
cd web
npm install
npm run build
cd ..
```

### 3. 启动服务

```bash
docker compose up -d
```

服务启动后：
- Web UI: `http://localhost:9191`
- API: `http://localhost:9191/api/`
- InfluxDB: `http://localhost:8086`

### 4. 初始化

```bash
# 初始化 InfluxDB Bucket 和降采样任务
docker compose exec backend python scripts/setup-influxdb.py

# 创建管理员账号
docker compose exec backend python manage.py create-admin
```

### 5. 部署 Agent

在 Center Web UI 中创建节点后，使用生成的部署命令在目标机器上安装 Agent。

或手动运行：

```bash
python -m agent.main \
    --server <center-host> \
    --port 9191 \
    --node-id <node-uuid> \
    --token <node-token>
```

## 项目结构

```
├── server/                # Center 后端
│   ├── api/               # REST API Blueprints
│   ├── models/            # SQLAlchemy 数据模型
│   ├── services/          # 业务逻辑层
│   ├── ws/                # WebSocket 命名空间
│   ├── utils/             # 工具函数
│   ├── app.py             # Flask App Factory
│   └── config.py          # 配置
├── agent/                 # Agent 端
│   ├── probes/            # 探测插件 (ICMP/TCP/UDP/HTTP/DNS)
│   ├── main.py            # Agent 入口
│   ├── ws_client.py       # WebSocket 客户端
│   ├── scheduler.py       # 任务调度器
│   ├── local_cache.py     # 本地 SQLite 缓存
│   └── config.py          # Agent 配置
├── web/                   # Vue 3 前端
│   └── src/
│       ├── api/           # Axios API 封装
│       ├── views/         # 页面视图
│       ├── stores/        # Pinia 状态管理
│       ├── composables/   # Vue Composables
│       ├── router/        # 路由
│       └── types/         # TypeScript 类型
├── scripts/               # 工具脚本
├── nginx/                 # Nginx 配置
├── docker-compose.yml     # Docker Compose
├── manage.py              # CLI 管理工具
└── requirements.txt       # Python 依赖
```

## 核心功能

- **多节点管理**: 创建/编辑/启停节点，自动生成认证 Token
- **探测任务**: 支持 5 种协议，可配置间隔(1-60s)、超时、目标类型
- **实时仪表盘**: WebSocket 推送，卡片式布局，按协议/标签/状态筛选
- **历史数据**: ECharts 时序图表，支持 30min-30天 多粒度查看
- **告警引擎**: 窗口评估 + 状态机，支持触发/恢复/冷却，Webhook 通知
- **权限模型**: admin / operator / readonly 三级角色
- **Agent 本地缓存**: 断线期间数据缓存，重连后批量补传
- **暗黑主题**: 支持明/暗主题一键切换

## CLI 命令

```bash
python manage.py create-admin       # 创建管理员
python manage.py remove-admin       # 删除管理员（至少保留一个）
python manage.py reset-password     # 重置用户密码
```

## 认证安全

- JWT 存储于 httpOnly Cookie（SameSite=Strict）
- 节点 Token 使用 bcrypt 哈希存储，仅创建时返回明文
- 登录失败 10 次锁定 15 分钟
- 所有 API 端点需认证（登录除外）

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

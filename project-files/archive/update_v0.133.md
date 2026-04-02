# v0.133.0 更新日志

**发布日期**: 2026-03-30

---

## 新增功能

### 1. MTR 路由追踪探测（核心功能）

新增 MTR (My Traceroute) 协议支持，提供三种子协议：

| 子协议 | 说明 | 默认端口 |
|--------|------|----------|
| **MTR (ICMP)** | 经典 ICMP 路由追踪 | - |
| **MTR (TCP)** | TCP 模式路由追踪 | 80 |
| **MTR (UDP)** | UDP 模式路由追踪 | 53 |

#### Agent 侧

- 新增 `agent/tools/mtr/monitor_mtr.py`：封装 `mtr --json` 命令，解析逐跳数据
- 新增 `agent/probes/mtr_probe.py`：实现 `MtrIcmpProbe`、`MtrTcpProbe`、`MtrUdpProbe` 三个探测插件
- 每次探测执行 5 个 ping/跳，返回完整路由链路数据（每跳含 host、loss%、last/avg/best/worst/stdev）
- 自动检测 `mtr` 命令可用性，不可用时在 capabilities 中标记为不支持
- Agent Docker 镜像新增 `mtr` 包（Dockerfile.agent）

#### Server 侧

- `VALID_PROTOCOLS` 新增 `mtr_icmp`、`mtr_tcp`、`mtr_udp`
- InfluxDB 写入新增 `hops` 字段（JSON 字符串），查询时自动反序列化
- WebSocket 实时推送包含 `hops` 数据
- ProbeTask.protocol 列宽度从 `String(10)` 扩展为 `String(20)`
- 启动时自动迁移 SQLite schema（无需手动操作）

#### WebUI

- **任务详情页**：MTR 协议显示仿 Linux 终端风格的逐跳路由表，包含：
  - 跳数 (#)、主机 (Host)、丢包率 (Loss%)、发送数 (Snt)
  - 最近延迟 (Last)、平均延迟 (Avg)、最佳 (Best)、最差 (Wrst)、标准差 (StDev)
  - 丢包行红色高亮、未知主机 (???) 灰色显示
  - 实时刷新（跟随 WebSocket 推送，每秒更新）
  - 同时保留上方时序图表（展示最终跳延迟趋势）
- **仪表盘**：协议筛选新增 MTR (ICMP)、MTR (TCP)、MTR (UDP)
- **任务管理**：协议选择新增三个 MTR 选项，TCP/UDP 模式支持指定端口
- **节点管理**：协议支持列新增 MTR 三种协议显示

### 2. ProbeResult 数据结构扩展

- `ProbeResult` 新增 `hops` 字段（`Optional[list]`），用于承载 MTR 逐跳数据
- `to_dict()` 方法自动序列化 hops
- 前端 `ProbeResult` 接口新增 `hops: MtrHop[] | null`
- 新增 `MtrHop` 接口定义

---

## 改进

### 3. 节点部署体验优化

- **Token 持久化**：节点创建时同时保存明文 Token（`token_plain` 字段），部署命令随时可查
- **移除一次性限制**：不再显示"Token 只会显示一次"的警告
- **部署按钮始终可用**：节点操作列始终显示「部署」按钮，不再仅限非在线状态
- **创建后直接展示部署命令**：创建节点后直接弹出部署对话框，格式与部署按钮一致
- **一键安装格式统一**：部署命令格式与 README「快速开始 — Agent」一节完全一致
  - 方式一：一键安装（推荐）
  - 方式二：Docker 安装（NAT 模式）
  - 方式三：Docker 安装（开放端口）
- **SQLite 自动迁移**：启动时自动添加 `token_plain` 列，无需手动操作

---

## 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `agent/tools/mtr/__init__.py` | MTR 工具包 |
| `agent/tools/mtr/monitor_mtr.py` | MTR 命令封装与 JSON 解析 |
| `agent/probes/mtr_probe.py` | MTR ICMP/TCP/UDP 三种探测插件 |
| `project-files/update_v0.133.md` | 本更新日志 |

### 修改文件

| 文件 | 变更说明 |
|------|----------|
| `version.py` | `0.132.0` → `0.133.0` |
| `agent/probes/base.py` | `ProbeResult` 新增 `hops` 字段，`to_dict()` 序列化 hops |
| `agent/probes/__init__.py` | 导入 `mtr_probe` 模块触发注册 |
| `Dockerfile.agent` | 新增 `mtr` 系统包 |
| `server/api/tasks.py` | `VALID_PROTOCOLS` 新增 mtr_icmp/mtr_tcp/mtr_udp |
| `server/models/task.py` | `protocol` 列宽度 `String(10)` → `String(20)` |
| `server/models/node.py` | 新增 `token_plain` 列 |
| `server/api/nodes.py` | 创建节点时保存明文 Token；部署命令直接包含真实 Token |
| `server/services/influx_service.py` | 写入/查询新增 hops JSON 字段 |
| `server/ws/agent_handler.py` | 实时推送包含 hops 数据 |
| `scripts/entrypoint.sh` | 启动时自动迁移 SQLite（添加 token_plain 列） |
| `web/src/types/index.ts` | ProbeTask.protocol 类型扩展；新增 MtrHop 接口；ProbeResult 新增 hops |
| `web/src/views/TaskDetailView.vue` | 新增 MTR 实时逐跳路由表 + MTR 图表 |
| `web/src/views/DashboardView.vue` | 协议筛选新增 MTR 选项 |
| `web/src/views/admin/TasksView.vue` | 协议选择新增 MTR 选项；端口需求扩展 |
| `web/src/views/admin/NodesView.vue` | 协议支持列新增 MTR；部署流程简化 |
| `README.md` | 版本号 0.133；协议列表新增 MTR |

---

## 部署步骤

### 服务端更新

```bash
cd /opt/NetworkStatus-Rabbit
bash update.sh
```

> update.sh 会自动检测前端变更并触发完整重建。
> SQLite schema 迁移在容器启动时自动执行。

### Agent 更新

```bash
cd /opt/networkstatus-agent
git pull
docker build -t nsr-agent -f Dockerfile.agent .
docker rm -f nsr-agent
# 重新启动（使用原有参数）
```

或使用一键安装脚本重新部署（会自动更新）。

---

## 兼容性说明

- **向后兼容**：已有的 ICMP/TCP/UDP/HTTP/DNS 任务不受影响
- **数据迁移**：SQLite schema 变更在启动时自动执行，无需手动操作
- **Agent 兼容**：旧版 Agent 不支持 MTR 协议，升级后 capabilities 中会自动报告 MTR 支持状态

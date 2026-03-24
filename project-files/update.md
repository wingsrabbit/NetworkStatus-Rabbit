# NetworkStatus-Rabbit 更新日志

---

## v0.127 (2026-03-24)

### Bug 修复

#### 问题 15：任务详情页异常区间标记 (markArea)
- 新增后端接口 `GET /api/data/task/<task_id>/alerts`，返回指定时间范围内的告警历史记录
- 详情页加载告警历史，将 alert→recovery 事件对转换为 ECharts `markArea` 半透明红色区域
- 活跃告警（未恢复）自动延伸到当前时间，持续可见
- 鼠标悬停异常区间可读出指标名称与持续时间
- 所有协议图表均支持 markArea 叠加

#### 问题 16：协议专属图表分化
- 新增后端接口 `GET /api/tasks/<task_id>`，返回单个任务详情（含 protocol）
- 详情页根据任务协议动态切换图表布局：
  - **ICMP**：延迟折线图 + 丢包率柱状图 + 抖动折线图
  - **TCP**：连接延迟折线图 + 连接成功率柱状图
  - **UDP**：延迟折线图 + 丢包率柱状图
  - **HTTP/HTTPS**：总响应时间折线图 + DNS/TCP/TLS/TTFB 阶段堆叠面积图 + HTTP 状态码散点图（按状态码段着色）
  - **DNS**：解析时间折线图 + 解析成功率柱状图 + 解析 IP 变更记录表格
- tooltip 根据协议和指标自动适配单位显示
- 前端 API 层新增 `getTask()` 和 `getTaskAlerts()` 函数

#### 问题 17：系统设置页面标题/副标题自定义
- 后端新增 `GET /api/settings/public` 公开接口（无需 admin），返回 `site_title` / `site_subtitle`
- 系统设置页新增"页面标题"和"页面副标题"输入表单项
- LayoutView 启动时加载公开设置，动态更新侧边栏品牌区和 `document.title`
- 管理员保存设置后立即刷新全局标题，无需手动刷新页面
- 前端 API 层新增 `getPublicSettings()` 函数

### 版本号更新
- `web/package.json` → 0.127.0
- `agent/ws_client.py` agent_version → 0.127.0

---

## v0.126 (2026-03-24)

### Bug 修复

#### 问题 1-2：探测核心统一接入 Network-Monitoring-Tools

- **文件**：`agent/network_tools/`（全部 5 个子模块）、`agent/probes/http_probe.py`、`agent/probes/dns_probe.py`、`agent/probes/icmp_probe.py`、`agent/probes/tcp_probe.py`、`agent/probes/udp_probe.py`
- **问题**：`agent/network_tools/` 中的实现不是来自上游 `Network-Monitoring-Tools`，而是本仓库自写代码占位；HTTP 和 DNS 探测直接在 `probes/` 层调用 `curl/requests/nslookup`，没有走 `network_tools/` 统一架构
- **修复**：
  - `network_tools/icmp_ping`、`tcp_ping`、`udp_ping` 添加上游 `Network-Monitoring-Tools` 引用注释，对齐上游解析逻辑
  - `udp_ping` 改用上游 `create_packet()/unpack_packet()` 的 struct 头格式（`!Id` = 4 字节序号 + 8 字节时间戳）
  - `network_tools/curl_ping/` **新建完整实现**：基于上游 `monitor_curl.py`，支持 curl `-w` 格式化输出解析 DNS/TCP/TLS/TTFB/总耗时，fallback 到 requests
  - `network_tools/dns_lookup/` **新建完整实现**：基于上游 `monitor_dns.py`，优先使用 `dig`（与上游一致），fallback 到 `nslookup`
  - `probes/http_probe.py` 重写为纯适配层，导入 `network_tools.curl_ping`
  - `probes/dns_probe.py` 重写为纯适配层，导入 `network_tools.dns_lookup`
  - 五类协议的探测入口全部统一收敛到 `agent/network_tools/`

#### 问题 3：任务同步状态机在 CRUD 变更时正确进入 pending

- **文件**：`server/api/tasks.py`
- **问题**：`create_task()`、`update_task()`、`delete_task()`、`toggle_task()` 只递增 `config_version`，不调用 `mark_sync_pending()`，导致日常任务变更不驱动同步状态机
- **修复**：四个 CRUD 端点在 `db.session.commit()` 之后统一调用 `task_service.mark_sync_pending(node_id, new_version)`

#### 问题 4：节点管理页展示协议支持状态

- **文件**：`web/src/views/admin/NodesView.vue`
- **问题**：节点列表缺少"协议支持"列，管理员看不到各节点 `capabilities` 信息
- **修复**：
  - 新增"协议支持"列，按 ICMP/TCP/UDP/HTTP/DNS 渲染 5 个标签
  - 支持的协议显示绿色 `NTag`，不支持的显示灰色
  - 不支持的协议鼠标悬停显示 `NTooltip`，展示 `unsupported_reasons` 原因
  - 导入 `NTooltip` 组件

#### 问题 5：任务创建时协议兼容性检查提示

- **文件**：`web/src/views/admin/TasksView.vue`
- **问题**：创建任务时不检查源节点是否支持所选协议，管理员无法提前知道任务是否可执行
- **修复**：
  - 新增 `protocolWarning` 响应式变量，`watch` 监听 `source_node_id` 和 `protocol` 变化
  - 当源节点不支持所选协议时，在协议选择下方显示 `NAlert` 警告，展示不支持原因
  - 警告不阻止创建，仅提供信息提示
  - 导入 `NAlert` 组件和 `watch`

#### 问题 6+10：WebSocket 事件命名统一为冒号协议

- **文件**：`agent/ws_client.py`、`server/ws/agent_handler.py`、`server/ws/dashboard_handler.py`、`server/app.py`、`server/api/tasks.py`、`web/src/composables/useSocket.ts`、`web/src/views/TaskDetailView.vue`
- **问题**：Agent-Center 主链路和 Dashboard 订阅链路使用下划线事件名（`agent_auth`、`center_task_sync`、`dashboard_subscribe_task` 等），与 PROJECT 7.1/7.3/7.6/7.8 规定的冒号命名不一致
- **修复**：
  - Agent 侧：所有 `emit` 和 `on` 事件名从 `agent_*`/`center_*` 改为 `agent:*`/`center:*`
  - Server 侧：`AgentNamespace` 和 `DashboardNamespace` 新增 `trigger_event()` 重写，将冒号事件名映射到下划线处理方法
  - Server 侧：所有 `emit()` 调用改为冒号格式（`center:auth_result`、`center:task_sync`、`dashboard:probe_snapshot` 等）
  - 前端：`useSocket.ts` 所有事件监听和发送改为冒号格式
  - 前端：`TaskDetailView.vue` 事件监听改为 `dashboard:task_detail`
  - 前端：新增 `connect_error` 中 `WS_AUTH_FAILED` 跳转登录页处理
  - 前端：新增 `error` 事件处理 `WS_AUTH_FAILED`/`WS_TOKEN_EXPIRED` 跳转登录页

#### 问题 7：UDP 能力发现自检改为检查 nc

- **文件**：`agent/probes/udp_probe.py`
- **问题**：UDP `self_test()` 只检查 Python `socket.AF_INET/SOCK_DGRAM` 是否可创建，不检查 PROJECT 11.5 要求的 `nc` 命令
- **修复**：`self_test()` 改为 `shutil.which('nc')` 检查 netcat 是否安装，`self_test_reason` 返回 `'nc (netcat) not installed'`

#### 问题 8：安装脚本交付完整 Agent 代码

- **文件**：`scripts/install-agent.sh`、`server/api/__init__.py`
- **问题**：安装脚本只创建 venv 和启动脚本，不下载 agent 代码，末尾提示"你需要自己把 agent Python code 复制到安装目录"
- **修复**：
  - Server 新增 `/api/agent-package.tar.gz` 端点，动态打包 `agent/` 目录和 `requirements-agent.txt` 为 tarball
  - 安装脚本新增从 center 下载 agent-package.tar.gz 并解压到安装目录的步骤
  - 安装脚本在解压后自动安装 `requirements-agent.txt` 依赖
  - 移除末尾 "NOTE: You need to copy..." 提示

#### 问题 9：告警历史接口加上 admin 权限

- **文件**：`server/api/alerts.py`、`web/src/router/index.ts`、`web/src/views/LayoutView.vue`
- **问题**：`GET /api/alerts/history` 使用 `@login_required` 而非 `@admin_required`，readonly 用户可访问管理区告警历史
- **修复**：
  - 后端 `/history` 路由装饰器改为 `@admin_required`
  - 前端路由 `admin/alerts/history` 添加 `meta: { requiresAdmin: true }`
  - LayoutView 中"告警历史"菜单移入 admin-only 条件块

#### 问题 11：节点状态机完整落地

- **文件**：`agent/ws_client.py`、`server/app.py`、`web/src/types/index.ts`、`web/src/views/admin/NodesView.vue`
- **问题**：Agent 断线后本地调度器不停止；心跳检查无节点上下线通知；前端只有 `online|offline` 两态
- **修复**：
  - Agent `on_disconnect` 新增 `self.scheduler.stop_all()` 调用，断线后立即停止所有探测任务
  - Server `heartbeat_checker` 在节点 offline 时通过 `push_alert()` 发送节点离线通知，online 恢复时发送上线通知
  - 前端 `Node.status` 类型扩展为 `'registered' | 'online' | 'offline' | 'disabled'`
  - NodesView 状态列支持四态渲染：已注册（黄）、在线（绿）、离线（红）、已禁用（灰）

#### 问题 12：告警状态机补齐 recovering 中间态

- **文件**：`server/services/alert_service.py`、`server/models/alert.py`（字段已存在）、`web/src/types/index.ts`
- **问题**：告警状态机只有 `normal|alerting` 两态，恢复时直接回 `normal`，无 `recovering` 中间态；`alert_history` 的 `message`、`alert_started_at`、`duration_seconds` 写库时全部为空
- **修复**：
  - 状态机扩展为 `normal -> alerting -> recovering -> normal`，recovering 状态下指标恢复正常则计入恢复计数，再次超限则退回 alerting
  - 新增 `_alert_started_at` 字典，告警触发时记录起始时间
  - `record_alert_event()` 填充 `message`（中文描述告警/恢复详情）、`alert_started_at`、`duration_seconds`（恢复时计算持续时长）
  - Webhook payload 增加 `message`、`alert_started_at`、`duration_seconds` 字段
  - 前端 `AlertHistory` 类型新增 `message`、`alert_started_at`、`duration_seconds` 字段

#### 问题 13：result_id 幂等去重升级为持久检查

- **文件**：`server/services/influx_service.py`
- **问题**：`check_result_exists()` 仅依赖 10 分钟 TTL 内存 `OrderedDict`，服务重启或长时补传会穿透去重
- **修复**：
  - 新增 SQLite 持久去重层（`data/dedup.db`），`written_results` 表记录已写入的 `result_id`
  - `check_result_exists()` 先查内存缓存（快路径），miss 后查 SQLite（慢路径），命中则回填内存缓存
  - `mark_result_written()` 同时写入内存缓存和 SQLite
  - `init_app()` 初始化时创建 dedup 数据库并清理 7 天前的过期条目
  - 内存缓存保留为性能优化层，SQLite 作为正确性保证层

#### 问题 14：Agent 本地缓存补齐 batch_id 和 retry_count 生命周期

- **文件**：`agent/local_cache.py`、`agent/ws_client.py`
- **问题**：`local_results` 表有 `batch_id` 和 `retry_count` 列但从未被使用，补传流程无法追踪批次和重试次数
- **修复**：
  - `local_cache.py` 新增 `set_batch_id(result_ids, batch_id)` 和 `increment_retry_count(result_ids)` 方法
  - `ws_client.py` `_backfill()` 在每个 chunk 发送前调用 `set_batch_id()` 关联批次 ID，调用 `increment_retry_count()` 累计重试次数

### 版本号更新

- `web/package.json` version：`0.125.0` → `0.126.0`
- `agent/ws_client.py` agent_version：`0.125.0` → `0.126.0`

---

## v0.125 (2026-03-24)

### Bug 修复

#### 问题 1：ICMP 抖动恢复 — 前端基于最近 10 个延迟点计算窗口抖动

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：v0.124 将 ICMP 探测改为 `count=1` 单次模型后，`_parse_jitter()` 无法从单包 ping 输出中解析 `mdev`，导致 `jitter` 恒为 `None`，前端抖动折线图和统计完全消失
- **修复**：
  - 新增 `computeWindowJitter()` 函数：对每个数据点 i，取 `[i-9, i]` 共 10 个有效 `latency` 值，计算标准差作为窗口抖动
  - 图表逻辑：优先使用后端返回的 jitter；若全为 null，回退到前端 10 点窗口计算
  - 新增 `avgWindowJitter` 计算属性，用于统计卡展示平均窗口抖动
  - 统计卡从 4 列扩展为 5 列（cols="2 m:5"），新增「窗口抖动」卡片，tooltip 说明计算口径
  - 图表中抖动系列名称从「抖动 (ms)」改为「窗口抖动 (ms)」，明确语义

#### 问题 2：Agent 探测层按 PROJECT 11.4 重构 — 补齐 network_tools 目录，UDP 回到真实探测模型

- **文件**：`agent/network_tools/`（新增）、`agent/probes/icmp_probe.py`、`agent/probes/tcp_probe.py`、`agent/probes/udp_probe.py`
- **问题**：Agent 没有按 PROJECT 11.4 要求将 Network-Monitoring-Tools-web 放在 `agent/network_tools/` 作为探测核心，`probes/*.py` 直接承担探测逻辑而非适配层。UDP 探测使用 `nc -u -z` 只做端口可达检测，不返回 `packet_loss` / `jitter`，指标无物理意义
- **修复**：
  - 新增 `agent/network_tools/` 目录，按 PROJECT 11.4 结构建立子模块：`icmp_ping/`、`tcp_ping/`、`udp_ping/`、`curl_ping/`、`dns_lookup/`
  - `icmp_ping`：将原 `icmp_probe.py` 中的 ping 解析逻辑迁入，probe 端只做适配
  - `tcp_ping`：将原 `tcp_probe.py` 中的 socket connect 逻辑迁入，probe 端只做适配
  - `udp_ping`：**全新实现**，基于 Python socket SOCK_DGRAM，发送 5 包 UDP 探测报文，逐包测量 RTT，支持 ICMP unreachable 回应和超时丢包检测，正式计算 `latency`（平均 RTT）、`packet_loss`（丢包率 %）、`jitter`（RTT 标准差）
  - UDP 自检从依赖 `nc` 改为依赖 Python socket，消除外部命令依赖
  - `probes/*.py` 统一收敛为纯适配层，只负责参数映射和 `ProbeResult` 归一化

#### 问题 3：任务编辑接口事务边界修复 — DB 保存与 Agent 下发状态解耦

- **文件**：`server/services/task_service.py`、`server/api/tasks.py`
- **问题**：`increment_config_version()` 内部自行 `db.session.commit()`，与调用方共享 session，导致任务变更被提前落库；后续 WebSocket 通知若抛异常，接口返回 500 但数据已入库
- **修复**：
  - `increment_config_version()` 移除内部 `commit()`，只修改 node 对象，事务提交权交回调用方
  - `tasks.py` 所有 CRUD 函数统一：先完成数据库变更 + commit，再 try/except 通知 Agent
  - `_notify_agent_task_change` 重命名为 `_try_notify_agent`，返回 `bool`；通知失败时响应中追加 `sync_status: 'pending'`，不再用 500 伪装成保存失败
  - `create_task`、`update_task`、`delete_task`、`toggle_task` 四个端点全部修复

#### 问题 4：任务编辑前端禁用后端不支持的字段

- **文件**：`web/src/views/admin/TasksView.vue`
- **问题**：编辑弹窗允许修改 `source_node_id`、`protocol`、`target_type`、`target_node_id`、`target_address`，但后端 `PUT /tasks/<id>` 不更新这些字段，用户修改后看似成功实则无效
- **修复**：
  - 编辑模式（`isEdit === true`）下，上述 5 个字段的控件统一添加 `:disabled="isEdit"`
  - 创建模式不受影响，仍可自由填写

### 版本号更新

- `web/package.json` version：`0.124.0` → `0.125.0`
- `agent/ws_client.py` agent_version：`0.124.0` → `0.125.0`

---

## v0.124 (2026-03-24)

### Bug 修复

#### 问题 1：缩放状态在数据刷新时不再被重置

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：用户拖动 `dataZoom` 进入局部区间后，新数据到达或定时刷新会调用 `setOption(..., true)` 整体覆盖图表配置（包括 xAxis min/max 和 dataZoom），导致缩放被强制打回全量视图
- **修复**：
  - 新增 `_chartInitialized` 标志和 `zoomStart`/`zoomEnd` 状态变量，记录当前缩放区间
  - 缩放态下 `updateChart()` 仅更新 `series` 数据（局部 `setOption`，不重建 xAxis/dataZoom），保持用户当前视图不变
  - 非缩放态或首次渲染时才执行完整 `setOption(..., true)`
  - `resetZoom()` 重置标志后触发完整刷新；`range` 切换时也重置缩放状态

#### 问题 2：ICMP 探测改为单次模型，与其他协议统一

- **文件**：`agent/probes/icmp_probe.py`
- **问题**：ICMP 探测写死 `count=4`（Windows `ping -n 4`，Linux `ping -c 4`），单轮探测耗时 3-4 秒，导致 `interval=1` 的任务实际 3-4 秒才出一条结果，与 tcp/udp/http/dns 的"一次调度循环 = 一条基础样本"规则不一致
- **修复**：
  - `count` 从 `4` 改为 `1`，每轮只发 1 个 echo request
  - ICMP 探测耗时降至毫秒级（正常网络），可配合 `interval=1` 实现接近 1Hz 的采样频率
  - `packet_loss` 变为 0% 或 100%（单包语义），`jitter` 由前端/服务端按窗口内多条结果计算

#### 问题 3：图表右边界增加安全尾巴，消除尾部假性掉点

- **文件**：`web/src/views/TaskDetailView.vue`、`server/api/data.py`
- **问题**：图表右边界直接对齐 `Date.now()`，导致尚在探测中或未到达超时阈值的样本时段被当作缺失数据，尾部总是像掉点
- **修复**：
  - 前端：图表 `effectiveEnd = now - tailMarginMs`，`tailMarginMs` 取自后端返回的 `timeout_seconds`（默认 10 秒），右边界不再贴到当前墙钟
  - 后端：`/task/<task_id>/stats` 的 `window_end` 改为 `now - timeout`，`expected_probes` 基于有效窗口计算
  - 图表、统计卡、理论点数三者使用同一套有效窗口，不再互相打架

#### 问题 4：补齐 3d/14d 时间范围 + 按规格对齐刷新节拍

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：前端只有 6 档范围（30m/1h/6h/24h/7d/30d），缺少 Project 6.2/10.3 规定的 `3d` 和 `14d`；刷新间隔是任意轮询（10s/15s/60s/300s），未按规格对齐
- **修复**：
  - `rangeOptions` 补齐为 8 档：30m/1h/6h/24h/3d/7d/14d/30d
  - 刷新节拍按 Project 规格对齐：30m~24h → 5 秒，3d~7d → 60 秒，14d~30d → 300 秒
  - `xAxisLabelFormat` 和 `tooltipFormat` 为 3d/14d 增加 `MM-dd HH:mm` 格式
  - 后端 bucket 选择已天然支持（≤24h→raw，≤7d→1m，>7d→1h）

#### 问题 5：数据点数按 bucket 粒度区分理论值 + tooltip 说明

- **文件**：`server/api/data.py`、`web/src/views/TaskDetailView.vue`
- **问题**：`expected_probes` 始终按原始采样间隔计算，在聚合视图（3d/7d/14d/30d）下理论值不匹配实际桶数，用户把分钟桶数误读成秒级掉点
- **修复**：
  - 后端新增 `_get_bucket_type()` 函数，返回 `raw`/`1m`/`1h`
  - `expected_probes` 按 bucket 粒度计算：raw → `range/interval`，1m → `range/60`，1h → `range/3600`
  - 前端统计卡显示 `实际 / 理论`，hover 时 tooltip 说明当前粒度（原始样本 / 分钟级聚合桶 / 小时级聚合桶）
  - `bucket_type` 和 `timeout_seconds` 字段同时返回给前端

### 版本号更新

- `web/package.json` version：`0.123.0` → `0.124.0`
- `agent/ws_client.py` agent_version：`0.123.0` → `0.124.0`

---

## v0.123 (2026-03-24)

### Bug 修复

#### 问题 1：图表底部布局修正 — dataZoom/图例/坐标轴不再重叠

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：`dataZoom` 滑动条、图例和坐标轴标签挤压在同一底部区域，三者互相覆盖导致信息显示不完整
- **修复**：
  - `legend.bottom` 从 `0` 调整为 `30`
  - `grid.bottom` 从 `70` 调整为 `96`
  - `dataZoom slider.bottom` 从 `24` 调整为 `8`
  - 图表容器高度从 `400px` 调整为 `430px`
  - 三层内容（图例 → 滑动条 → 底边）间距分明，不再重叠

#### 问题 2：`最后更新` 语义修正 — 不再因定时轮询误标为新数据

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：`fetchData()` 每次成功都调用 `__nsr_markDataReceived()`，导致即使定时重拉到同批旧数据，页脚"最后更新"也被重置为"10秒内"，不再准确反映新探测结果到达时间
- **修复**：
  - 从 `fetchData()` 中移除 `__nsr_markDataReceived()` 调用
  - 仅保留 `handleRealtimeUpdate()` 中的调用，确保"最后更新"严格绑定实时 WebSocket 新结果到达
  - 首屏加载和定时重拉不再错误地刷新页脚新鲜度标记

#### 问题 3：Agent 调度器修正 — 从串行等待改为固定节拍

- **文件**：`agent/scheduler.py`
- **问题**：`_task_loop()` 采用"执行探测 → 等待 interval"的串行模型，实际周期 = 探测耗时 + interval，导致 `interval=1` 的任务实际采样频率低于 1Hz，`total_probes` 明显少于理论值
- **修复**：
  - 引入 `next_run` 固定节拍变量，基于 `time.monotonic()` 计算下一次运行时间
  - 每次探测完成后 `next_run += interval`，实际等待 `max(0, next_run - now)`
  - 若探测耗时超过 interval（过载），重置节拍避免连续突发，并记录 debug 日志
  - 理想情况下采样周期等于配置的 interval，不再受探测耗时影响

#### 问题 4：数据点数展示增强 — 显示 `实际/理论` 双值

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：前端仅显示后端 `total_probes`（实际记录数），未使用 v0.122 已返回的 `expected_probes`（理论次数），用户无法判断是否存在采样偏差
- **修复**：
  - 数据点数统计卡改为显示 `实际 / 理论` 格式，如 `1692 / 1800`
  - 当 `expected_probes` 不可用时降级为仅显示 `total_probes`

### 版本号更新

- `web/package.json` version：`0.122.0` → `0.123.0`
- `agent/ws_client.py` agent_version：`0.122.0` → `0.123.0`

---

## v0.122 (2026-03-24)

### Bug 修复

#### 问题 1+3：统计卡数据来源统一 — 所有范围以服务端为准

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：原始视图（30m/1h/6h/24h）的统计卡通过前端 `recalcStats()` 从本地 `points.value` 重算，受 500 条裁剪限制影响，与图表当前窗口数据脱节；长周期视图则依赖定时 `fetchData()` 从服务端拉取。两套来源不一致。
- **修复**：
  - 移除 `recalcStats()` 函数及其在 `handleRealtimeUpdate()` 中的调用
  - 所有范围统一通过定时 `fetchData()` 从服务端获取统计和数据，差别仅在刷新频率：30m/1h 每 10 秒、6h/24h 每 15 秒、7d 每 60 秒、30d 每 5 分钟
  - 实时 WebSocket 推送仅负责图表视觉平滑追加，不再影响统计卡数据
  - 统计卡始终展示服务端按完整时间窗口计算的结果

#### 问题 2：数据点数语义明确化 + 后端补充窗口元数据

- **文件**：`server/api/data.py`
- **问题**：`/data/task/<task_id>/stats` 接口仅返回 `total_probes`，缺少任务采样周期、窗口起止时间、理论点数等信息，前端无法准确展示"当前窗口内的实际记录次数"
- **修复**：
  - 在 stats 响应中新增 `interval_seconds`（任务采样间隔）、`window_start`、`window_end`（窗口起止时间）、`expected_probes`（理论记录次数 = 窗口时长 / 间隔）
  - `total_probes` 保留为实际记录次数，前端直接展示
  - 新增 `_parse_range_to_seconds()` 辅助函数用于窗口计算

#### 问题 4+5：图表框选缩放 + 重置按钮

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：图表无法框选放大查看局部细节，且无法从局部视图返回基础视图
- **修复**：
  - 在 ECharts `setOption()` 中新增 `dataZoom` 配置：`inside`（鼠标滚轮/触控缩放）+ `slider`（底部滑动条）
  - 新增 `isZoomed` 状态变量，通过监听 `datazoom` 事件追踪缩放状态
  - 在时间范围下拉旁新增"重置缩放"按钮（`NButton`），仅在缩放状态下显示
  - 点击重置按钮调用 `resetZoom()` 恢复到当前 range 的完整视图
  - `grid.bottom` 调整为 70px 以容纳滑动条

### 版本号更新

- `web/package.json` version：`0.121.0` → `0.122.0`
- `agent/ws_client.py` agent_version：`0.121.0` → `0.122.0`

---

## v0.121 (2026-03-24)

### 新增功能

#### 底部全局状态栏

- **文件**：`web/src/views/LayoutView.vue`
- **需求**：参考 status.wingsrabbit.com，在全站布局底部居中增加状态栏
- **实现**：
  - 显示 `Powered by NetworkStatus-Rabbit · 现在时间（GMT+8）：YY/MM/DD HH:mm:ss · 最后更新：10秒内`
  - GMT+8 时间每秒刷新
  - 最后更新基于最近收到数据的时间，<10 秒显示 `10秒内`，否则显示 `N秒前`
  - 引入 dayjs/plugin/utc + dayjs/plugin/timezone 实现时区转换
  - 通过 `window.__nsr_markDataReceived()` 全局标记数据到达时间

### Bug 修复

#### 问题 7：7 天 / 30 天页面不会自动更新

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：v0.12 中为 7d/30d 禁用了秒级实时追加，但未补充替代刷新机制，导致长周期视图必须手动切换或刷新才能看到新数据
- **修复**：新增 `_refreshTimer` 定时刷新 —— 7d 视图每 60 秒自动重拉数据，30d 视图每 300 秒自动重拉数据；切换 range 时自动重置定时器；组件卸载时清理

#### 问题 8：30 分钟~24 小时在历史不足时应保留空白

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：ECharts 使用 `category` 类型横轴，只渲染已有数据点的时间范围，导致 30m/1h/24h 在数据不足时看起来完全相同，时间轴左边界随数据前移让用户误以为"被困在一小段数据里"
- **修复**：
  - 将 xAxis 从 `type: 'category'` 改为 `type: 'time'`
  - 固定时间窗口为 `min = now - rangeMs`，`max = now`
  - 数据改为 `[timestamp, value]` 二维数组格式
  - 数据不足的区间自然留白，用户可直观看到数据记录的起始时间
  - 不同 range 使用不同的 axisLabel 格式（`HH:mm:ss` / `HH:mm` / `MM-dd HH:mm`）
  - tooltip 也改为从 `value[0]` 读取时间并按 range 格式化

### 版本号更新

- `web/package.json` version：`0.12.0` → `0.121.0`
- `agent/ws_client.py` agent_version：`0.12.0` → `0.121.0`

---

## v0.12 (2026-03-24)

### Bug 修复

#### P0：Agent 时间戳格式错误（已在上一轮修复）

- **文件**：`agent/ws_client.py`
- **问题**：`timestamp.isoformat() + 'Z'` 对带时区的 UTC datetime 产生非法字符串 `+00:00Z`，导致 InfluxDB 写入失败，任务详情页历史数据为空
- **修复**：改为 `timestamp.isoformat().replace('+00:00', 'Z')`，输出标准 RFC3339 格式

#### P0：实时消息结构不一致（已在上一轮修复）

- **文件**：`server/ws/agent_handler.py`
- **问题**：`push_task_detail()` 将 agent 原始包（`metrics` 嵌套结构）透传给前端，前端期望扁平的 `ProbeResult`，导致图表无折线 + `Invalid Date`
- **修复**：将 `metrics` 字段展平为与前端 `ProbeResult` 一致的扁平结构后再推送

#### 问题 1：统计卡不随实时数据更新

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：实时更新只执行 `points.push()` + `updateChart()`，不重算统计值，导致平均延迟 / P95 / 丢包 / 点数在进入页面后静止不动
- **修复**：新增 `recalcStats()` 函数，在每次实时追加后从当前 `points` 重新计算统计值并更新 `stats`

#### 问题 2：30 分钟到 24 小时切换缺少可感知差异

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：所有时间范围统一使用 `HH:mm:ss` 横轴格式，无法区分时间跨度
- **修复**：根据 range 选择不同格式 —— `30m/1h/6h` 用 `HH:mm:ss`，`24h` 用 `HH:mm`，`7d/30d` 用 `MM-DD HH:mm`

#### 问题 3：7 天 / 30 天视图混入秒级实时点

- **文件**：`web/src/views/TaskDetailView.vue`
- **问题**：实时 WebSocket 推送的秒级数据在所有 range 下无差别追加，破坏 7d/30d 的聚合粒度语义
- **修复**：新增 `isRawRange` 计算属性，仅 `30m/1h/6h/24h`（raw 粒度）允许实时追加，7d/30d 视图忽略实时推送

#### 问题 4：7 天 / 30 天聚合数据链路无兜底

- **文件**：`server/services/influx_service.py`
- **问题**：当 InfluxDB 的 `agg_1m` / `agg_1h` 降采样任务未正常运行时，长周期查询直接返回空数据
- **修复**：新增 fallback 逻辑 —— 若聚合 bucket 查询结果为空，自动从 `raw` bucket 使用 `aggregateWindow()` 做服务端即时聚合

#### 问题 5：前端数值展示小数位不统一

- **文件**：`web/src/views/TaskDetailView.vue`、`web/src/views/DashboardView.vue`
- **问题**：统计卡用 `toFixed(1)`（一位小数），tooltip 不格式化（暴露浮点误差如 `0.21000000000000002`），Dashboard 丢包直接显示原始值
- **修复**：
  - 统计卡全部改用 `toFixed(2)`（两位小数）
  - 图表 tooltip 新增自定义 `formatter`，所有数值统一两位小数
  - Dashboard 的 `formatLatency` 和丢包展示均改为两位小数

### 版本号更新

- `web/package.json` version：`0.1.0` → `0.12.0`
- `agent/ws_client.py` agent_version：`0.1.0` → `0.12.0`
- 前端侧栏通过 `__APP_VERSION__` 自动展示当前版本号

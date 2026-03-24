# NetworkStatus-Rabbit 更新日志

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

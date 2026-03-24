# NetworkStatus-Rabbit 更新日志

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

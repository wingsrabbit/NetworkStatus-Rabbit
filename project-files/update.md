# NetworkStatus-Rabbit 更新日志

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

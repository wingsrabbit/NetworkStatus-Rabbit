# v0.12 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 修复 Agent 时间戳格式错误。
   - `agent/ws_client.py` 原先会生成非法的 `+00:00Z` 时间戳，导致 InfluxDB 写入失败。
   - 修复后统一输出标准 RFC3339 UTC 时间戳。

2. 修复实时消息结构不一致。
   - `server/ws/agent_handler.py` 之前把带 `metrics` 嵌套的原始包直接推给前端。
   - 修复后将结构展平成前端需要的 `ProbeResult` 形状。

3. 统计卡改为随实时数据更新。
   - `web/src/views/TaskDetailView.vue` 新增重算逻辑，实时追加数据后同步更新平均延迟、P95、丢包和点数。

4. 各时间范围使用不同横轴格式。
   - `30m/1h/6h` 使用 `HH:mm:ss`
   - `24h` 使用 `HH:mm`
   - `7d/30d` 使用 `MM-DD HH:mm`

5. 长周期视图不再混入秒级实时点。
   - 仅 raw 粒度范围允许实时追加。
   - 7d 和 30d 视图改为忽略实时秒级点。

6. 长周期聚合查询增加兜底。
   - `server/services/influx_service.py` 新增 fallback：聚合 bucket 为空时，从 raw bucket 即时聚合。

7. 数值展示统一保留两位小数。
   - 统计卡、tooltip、Dashboard 中的延迟与丢包显示全部统一口径。

## 版本变更

1. `web/package.json`：0.1.0 → 0.12.0
2. `agent/ws_client.py` 上报版本：0.1.0 → 0.12.0
3. 前端侧边栏开始展示当前版本号
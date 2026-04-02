# v0.124 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 缩放状态在刷新时不再丢失。
   - `web/src/views/TaskDetailView.vue` 增加 `_chartInitialized`、`zoomStart`、`zoomEnd`，缩放态下仅更新 series。

2. ICMP 探测改为单次模型。
   - `agent/probes/icmp_probe.py` 的 `count` 从 4 改为 1。
   - 每轮调度只生成一个基础样本，更接近其他协议的行为。

3. 图表右边界增加安全尾巴。
   - 详情页右侧时间边界不再直接贴着当前墙钟，减少尾部假掉点。
   - `server/api/data.py` 和前端统一使用有效窗口口径。

4. 补齐 3d 和 14d 时间范围，并重新对齐刷新节拍。
   - 原始设计为 8 档范围。
   - 长周期刷新策略按窗口重分级。

5. 数据点数按 bucket 粒度计算理论值。
   - 后端新增 bucket 类型识别。
   - 前端 tooltip 能区分原始样本、分钟桶和小时桶。

## 版本变更

1. `web/package.json`：0.123.0 → 0.124.0
2. `agent/ws_client.py` 上报版本：0.123.0 → 0.124.0
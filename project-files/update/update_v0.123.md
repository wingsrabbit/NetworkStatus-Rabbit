# v0.123 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 修正图表底部布局。
   - `web/src/views/TaskDetailView.vue` 调整 legend、grid、dataZoom 位置和图表高度。
   - 解决图例、滑动条和坐标轴重叠问题。

2. 修正“最后更新”语义。
   - 定时重拉数据不再被误判为新样本到达。
   - 只有实时 WebSocket 新结果真正到达时才刷新页脚状态。

3. Agent 调度器改为固定节拍调度。
   - `agent/scheduler.py` 引入 `time.monotonic()` 和 `next_run`。
   - 实际采样周期不再等于“探测耗时 + interval”。

4. 数据点数改为显示“实际 / 理论”。
   - 前端开始同时展示 `total_probes` 和 `expected_probes`。

## 版本变更

1. `web/package.json`：0.122.0 → 0.123.0
2. `agent/ws_client.py` 上报版本：0.122.0 → 0.123.0
# v0.122 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 统计卡数据来源统一改为服务端计算。
   - `web/src/views/TaskDetailView.vue` 移除本地实时重算口径。
   - 所有范围都通过定时 `fetchData()` 使用服务端统计结果。

2. 后端 stats 接口补充窗口元数据。
   - `server/api/data.py` 新增 `interval_seconds`、`window_start`、`window_end`、`expected_probes` 等字段。
   - 前端可以区分理论点数与实际点数。

3. 任务详情页加入图表框选缩放与重置按钮。
   - `web/src/views/TaskDetailView.vue` 新增 `dataZoom` 配置。
   - 增加 `isZoomed` 状态和“重置缩放”按钮。

## 版本变更

1. `web/package.json`：0.121.0 → 0.122.0
2. `agent/ws_client.py` 上报版本：0.121.0 → 0.122.0
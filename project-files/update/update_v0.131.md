# v0.131 更新日志

日期：2026-03-28

来源：由 `project-files/update_v0.131.md` 整理。

## Bug 修复

1. 修复前端聚合数据失败标记不显示。
   - `web/src/views/TaskDetailView.vue` 新增统一失败判断 helper，同时兼容 boolean 和数值型 success。

2. 修复非法 range 参数导致 500。
   - 原设计为在 `server/api/data.py` 对 range 做正则校验，非法输入返回 400。

3. 修复 HTTP 计时字段累积值误叠加。
   - `agent/probes/http_probe.py` 与 `agent/tools/curl_ping/monitor_curl.py` 改为计算增量时间：tcp、tls、ttfb。

4. 修复 InfluxDB 下采样任务字段不完整。
   - 设计目标是让 success 和 HTTP 阶段时间也参与聚合。

5. 清理 compose 配置。
   - `docker-compose.yml` 移除废弃的 `version: '3.8'`。

## 说明

这份更新日志是历史记录。当前代码是否完全兑现其中第 2 和第 4 条，需要以当前代码现状为准。
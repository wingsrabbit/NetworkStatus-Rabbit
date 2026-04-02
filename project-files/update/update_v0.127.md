# v0.127 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复与新增

1. 任务详情页支持异常区间标记。
   - 新增 `GET /api/data/task/<task_id>/alerts`。
   - 前端将 alert → recovery 对转换为 ECharts `markArea`。

2. 详情页图表按协议分化。
   - 新增 `GET /api/tasks/<task_id>`。
   - ICMP、TCP、UDP、HTTP、DNS 分别展示不同图层和指标组合。

3. 系统设置支持站点标题和副标题。
   - 新增公开接口 `GET /api/settings/public`。
   - Layout 启动时动态加载标题并更新 `document.title`。

## 版本变更

1. `web/package.json`：0.126.0 → 0.127.0
2. `agent/ws_client.py` 上报版本：0.126.0 → 0.127.0
# v0.121 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 新增功能

1. 新增全局底部状态栏。
   - `web/src/views/LayoutView.vue` 在全站底部显示 Powered by、GMT+8 当前时间和“最后更新”状态。
   - 引入 `window.__nsr_markDataReceived()` 作为全局数据到达标记。

## 核心修复

1. 修复 7 天和 30 天页面不会自动更新的问题。
   - `web/src/views/TaskDetailView.vue` 增加长周期定时刷新。
   - 7d 每 60 秒刷新，30d 每 300 秒刷新。

2. 修复 30 分钟到 24 小时在历史不足时无法体现时间跨度的问题。
   - 横轴从 `category` 改为 `time`。
   - 固定窗口左边界与右边界，数据不足部分自然留白。
   - 不同范围使用不同的标签与 tooltip 时间格式。

## 版本变更

1. `web/package.json`：0.12.0 → 0.121.0
2. `agent/ws_client.py` 上报版本：0.12.0 → 0.121.0
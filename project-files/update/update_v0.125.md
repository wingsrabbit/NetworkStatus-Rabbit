# v0.125 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 恢复 ICMP 抖动展示。
   - `web/src/views/TaskDetailView.vue` 新增基于最近 10 个延迟样本的窗口抖动计算。
   - 统计卡新增“窗口抖动”。

2. Agent 探测层按 Project 11.4 重构。
   - 新增 `agent/network_tools/` 目录。
   - ICMP/TCP/UDP 逻辑下沉为底层模块，probe 只做适配。
   - UDP 改回真实探测模型，能够给出 RTT、丢包和抖动。

3. 任务编辑接口事务边界修复。
   - `server/services/task_service.py` 的 `increment_config_version()` 不再自己提交事务。
   - `server/api/tasks.py` 统一先落库，再尝试通知 Agent。
   - 通知失败只返回 `sync_status: pending`，不再伪装成保存失败。

4. 前端编辑任务时禁用后端不支持修改的字段。
   - 避免用户改了源节点、协议、目标类型后界面显示成功但后端实际未改。

## 版本变更

1. `web/package.json`：0.124.0 → 0.125.0
2. `agent/ws_client.py` 上报版本：0.124.0 → 0.125.0
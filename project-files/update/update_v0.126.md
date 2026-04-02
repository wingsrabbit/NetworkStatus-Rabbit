# v0.126 更新日志

日期：2026-03-24

来源：由 `project-files/update.md` 拆分整理。

## 核心修复

1. 探测核心统一接入 Network-Monitoring-Tools。
   - `agent/network_tools/` 五个协议子模块完成接入。
   - HTTP、DNS 也回到统一底层目录，不再散落在 probe 层直接调用系统命令。

2. 任务同步状态机在任务 CRUD 时真正进入 pending。
   - `server/api/tasks.py` 四个接口统一在提交后调用 `mark_sync_pending()`。

3. 节点管理页补齐协议支持状态展示。
   - `web/src/views/admin/NodesView.vue` 新增能力列。

4. 任务创建页增加协议兼容性提示。
   - `web/src/views/admin/TasksView.vue` 对源节点能力做 warning 展示。

5. Center-Agent 与 Dashboard 的 WebSocket 事件名统一切回冒号协议。
   - 统一为 `agent:*`、`center:*`、`dashboard:*`。

6. UDP 能力发现标准改为检查 netcat。
   - `agent/probes/udp_probe.py` 的自检按 `nc` 是否存在执行。

7. Agent 安装脚本开始交付完整代码。
   - 服务端新增 `agent-package.tar.gz` 下载端点。
   - 安装脚本自动下载、解压并安装依赖。

8. 告警历史管理接口收紧为 admin 权限。

9. 节点状态机补齐断线停任务与上下线通知语义。

10. 告警状态机补齐 recovering 中间态，并开始落完整告警历史字段。

11. result_id 去重升级为持久层实现。
   - 新增 `data/dedup.db` 与 `written_results`。

12. Agent 本地缓存正式接入 `batch_id` 和 `retry_count` 生命周期。

## 版本变更

1. `web/package.json`：0.125.0 → 0.126.0
2. `agent/ws_client.py` 上报版本：0.125.0 → 0.126.0
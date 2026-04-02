# v0.133 更新日志

日期：2026-03-30

来源：由 `project-files/update_v0.133.md` 整理。

## 新增功能

1. 新增 MTR 路由追踪探测。
   - 支持 `mtr_icmp`、`mtr_tcp`、`mtr_udp` 三种协议。
   - Agent 增加 `agent/tools/mtr/monitor_mtr.py` 与 `agent/probes/mtr_probe.py`。

2. `ProbeResult` 数据结构扩展。
   - 增加 `hops` 和前端 `MtrHop` 类型。
   - 支持承载逐跳路由数据。

## 服务端改动

1. `VALID_PROTOCOLS` 增加三种 MTR 协议。
2. InfluxDB 写入与查询增加 `hops` JSON 字段。
3. WebSocket 实时推送包含 `hops`。
4. `ProbeTask.protocol` 列宽从 10 扩到 20。
5. 启动时自动迁移 SQLite schema。

## 前端改动

1. 任务详情页增加 MTR 终端风格逐跳表。
2. 仪表盘协议筛选增加三种 MTR。
3. 任务管理增加三种 MTR 选项。
4. 节点管理协议支持列加入三种 MTR。

## 部署体验优化

1. 节点创建时保存 `token_plain`，部署命令可重复查看。
2. 节点列表中的部署按钮始终可用。
3. 创建节点后直接弹出部署命令。

## 版本变更

1. `version.py`：0.132.0 → 0.133.0
2. README 协议列表加入 MTR
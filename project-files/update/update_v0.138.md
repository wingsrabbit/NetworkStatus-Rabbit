# v0.138.0 更新日志

**日期**：2026-04-05

## 核心改动：MTR 持久进程架构

### 问题背景

v0.137 的 MTR 实现每次探测周期都启动一个新的 `mtr --json -c 1` 进程，前端需要在客户端累积合并所有历史结果来计算统计数据。这导致：
- 每次 `probe()` 都有进程启动开销
- 前端 `mergeHops()` + Welford 算法逻辑复杂且易出 bug（v0.135 重置问题的根因）
- 重置后 fetchData 自动刷新把旧数据合并回来，导致"重置无效"
- Snt 值依赖前端累积，刷新页面后从零开始

### 解决方案

改为 **Agent 端持久 mtr 进程** 架构：

1. **Agent**: 每个 MTR 任务启动一个长期运行的 `mtr --raw -i 1 target` 进程
2. Agent 实时解析 raw 流式输出，使用 Welford 在线算法累积统计
3. 每个探测间隔（默认 5s）对当前累积状态做快照，作为 ProbeResult 发送
4. 重置时 kill 进程 → 清零状态 → 启动新进程，Snt 从 0 开始
5. 进程意外退出时自动重启

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `agent/tools/mtr/persistent_mtr.py` | **新增** | PersistentMtr 类 — 管理长运行 mtr 进程 + raw 输出解析 + 统计累积 |
| `agent/scheduler.py` | 修改 | 新增 `_mtr_task_loop()`，MTR 协议走持久进程分支 |
| `agent/probes/mtr_probe.py` | 未改动 | 保留用于 self_test，probe() 不再被 MTR 任务调用 |
| `web/src/views/TaskDetailView.vue` | 修改 | 移除前端累积逻辑（CumHopState/mergeHops），直接展示最新快照 |
| `version.py` | 修改 | 0.137.0 → 0.138.0 |
| `web/package.json` | 修改 | 0.137.0 → 0.138.0 |

### 技术细节

**Round 检测算法**：`mtr --raw` 不输出丢包行，通过 `_current_round_max_hop` 回绕检测推算 round 数。当 hop number ≤ 当前 round 已见的最大 hop，判定为新 round 开始。所有 hop 的 `sent = total_rounds`（与 mtr 原生行为一致）。

**前端简化**：移除 CumHopState 接口、mergeHops 函数、mtrInitialMergeDone 标志。mtrDisplayHops 直接从 mtrLatestHops（最新快照）派生，无需跨结果累积。

### 验证清单

- [ ] MTR ICMP 任务创建后 Snt 持续增长
- [ ] MTR TCP 任务创建后 Snt 持续增长
- [ ] MTR UDP 任务创建后 Snt 持续增长
- [ ] 点击"重置统计"后 Snt 从 0 重新开始
- [ ] 重置后无旧数据残留
- [ ] 刷新页面后数据保持（不从零开始）
- [ ] Agent 重连后 MTR 任务正常恢复
- [ ] ICMP/TCP/UDP 等非 MTR 协议不受影响

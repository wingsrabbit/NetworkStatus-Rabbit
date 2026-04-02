# v0.136.0 更新日志

**日期**: 2026-04-02

## Bug 修复

### MTR 任务开始时间不显示
- **问题**: 当任务刚创建且无数据点时(`points.length === 0`)，`mtrStartTime` 不会被设置，导致"开始于"时间不显示。只有重置后才会显示。
- **根因**: `fetchData()` 中的 `if (isMtr.value && points.value.length > 0)` 条件在无数据时跳过了 `mtrStartTime` 的设置。
- **修复**: 在 `onMounted` 中获取任务信息后立即设置 `mtrStartTime`，不依赖数据点是否存在。

### MTR 重置时间刷新后丢失
- **问题**: 重置时间仅存储在前端内存中，页面刷新或重新进入后丢失，导致 SNT 计数从任务创建时开始累计而非从重置时间开始。
- **根因**: `mtrStartTime` 只通过 WebSocket 推送设置，没有持久化到数据库。
- **修复**: 
  1. 后端 `ProbeTask` 模型新增 `mtr_reset_time` 字段。
  2. 重置操作时将时间写入数据库。
  3. 前端加载时从 `task.mtr_reset_time` 恢复重置时间。
  4. 自动迁移脚本在启动时为已有数据库添加新列。

## 新功能

### MTR 任务开始时间始终显示
- 任务创建后立即显示"开始于 YYYY-MM-DD HH:mm:ss"。
- 点击重置按钮后更新为重置时间。
- 刷新、重进页面后保持显示正确的时间。

### MTR 数据在后台持续累积
- 任务启动后 Agent 侧持续运行、持续写 InfluxDB。
- 用户打开详情页时从 InfluxDB 加载历史数据，SNT 反映真实累计量。
- 重置后仅累计重置时间之后的数据点。

## 变更文件

| 文件 | 变更 |
|------|------|
| `server/models/task.py` | 新增 `mtr_reset_time` 字段，`to_dict()` 输出该字段 |
| `server/app.py` | 新增 `_auto_migrate()` 为已有数据库添加 `mtr_reset_time` 列 |
| `server/ws/dashboard_handler.py` | 重置时持久化 `mtr_reset_time` 到数据库 |
| `web/src/types/index.ts` | `ProbeTask` 接口新增 `mtr_reset_time` |
| `web/src/views/TaskDetailView.vue` | 优化 `mtrStartTime` 初始化逻辑、使用持久化重置时间 |
| `version.py` | 0.135.0 → 0.136.0 |
| `web/package.json` | 0.135.0 → 0.136.0 |

## 覆盖范围

- MTR ICMP / TCP / UDP 三种协议共享同一套代码路径，均已覆盖。

## 待验证

- [ ] 新建 MTR 任务后"开始于"立即显示
- [ ] 页面刷新后 SNT 反映累计值
- [ ] 重置后 SNT 从 0 重新累计
- [ ] 重置后刷新页面仍显示重置时间
- [ ] 三种 MTR 协议均工作正常

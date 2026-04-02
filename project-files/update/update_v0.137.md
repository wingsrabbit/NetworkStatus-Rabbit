# v0.137.0 更新日志

**日期**: 2026-04-02

## Bug 修复

### MTR SNT 刷新/重入后丢失（竞态条件）
- **问题**: 打开 MTR 详情页后 SNT 正常累加，但 F5 刷新或重新进入页面后 SNT 回退。ICMP 表现为 SNT 变成 1，TCP 表现为丢失最近几个数据点（如 182 → 180）。
- **根因**: `onMounted` 中 `fetchData()` 未被 `await`，而 `subscribeTask()` + WebSocket 监听在 `fetchData` 返回前就已注册。WebSocket 推送先于 API 响应到达 → `mergeHops` 被调用 → `mtrCumState.size > 0` → 后续 API 数据的 merge 分支被跳过，导致只保留了 WebSocket 推送的 1-2 个数据点。
- **修复**:
  1. `onMounted` 中 `await fetchData()` 确保 API 数据加载完成后再订阅 WebSocket。
  2. 新增 `mtrInitialMergeDone` 标志位替代 `mtrCumState.size === 0` 判断，精确控制初始合并逻辑。
  3. 初始加载时清空 `mtrCumState` 后从 API 数据完整重建，`mtrInitialMergeDone` 置为 `true`。
  4. 重置操作时将 `mtrInitialMergeDone` 置为 `false`，触发下次 `fetchData` 重建。

## 变更文件

| 文件 | 变更 |
|------|------|
| `web/src/views/TaskDetailView.vue` | 修复竞态：await fetchData、mtrInitialMergeDone 标志位、重置后重建逻辑 |
| `version.py` | 0.136.0 → 0.137.0 |
| `web/package.json` | 0.136.0 → 0.137.0 |

## 技术细节

### 竞态时序分析（修复前）
```
onMounted()
  ├─ subscribeTask()          ← WebSocket 立即注册
  ├─ socket.on(...)           ← 开始接收推送
  ├─ fetchData() [未 await]   ← API 请求发出但未完成
  │
  │   WebSocket 推送到达 → mergeHops() → mtrCumState.size = 1
  │
  └─ fetchData 完成 → mtrCumState.size > 0 → 跳过 API 数据合并
                       ↑ 只有 1 个 WebSocket 数据点
```

### 修复后时序
```
onMounted()
  ├─ await fetchData()        ← 阻塞直到 API 数据加载完成
  │   └─ mtrInitialMergeDone = false → 清空 Map → 合并所有 API 点
  │   └─ mtrInitialMergeDone = true
  ├─ subscribeTask()          ← API 数据已就绪后才订阅
  └─ socket.on(...)           ← 后续 WebSocket 增量追加
```

## 覆盖范围

- MTR ICMP / TCP / UDP 三种协议共享同一套代码路径，均已覆盖。

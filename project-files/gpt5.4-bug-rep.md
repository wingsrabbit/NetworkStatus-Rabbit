# NetworkStatus-Rabbit Bug Report Merge

## 一、报告说明

本报告基于以下三份来源合并整理：

1. 本地审查文件：`project-files/GPT5.4-findbug-01.md`
2. 仓库文件：`project-files/GPT5.4-findbug-01.md`
3. 仓库文件：`project-files/gpt-5.4-findbug-01.md`

本次不是简单拼接，而是做了二次核对：

1. 以当前仓库代码为准重新核查关键问题
2. 以当前 `PROJECT.md v1.5` 为最终规格基准
3. 合并重合项
4. 保留互补项
5. 剔除与当前规格不一致、或明显来自旧审查上下文的结论

因此，这份文档可视为本轮更可靠的统一版 Bug 总报告。

---

## 二、总判断

### 1. 主题没有跑偏

当前项目**没有明显偏到服务器状态监控**方向。

没有发现实现 CPU、内存、磁盘、系统负载一类与本项目目标冲突的核心功能，因此项目主线仍然是：

1. 网络质量探测
2. 中心汇总存储
3. Dashboard / 任务详情展示
4. WebSocket 实时推送
5. 告警与补传

### 2. 主要问题不是“产品方向错了”，而是“规格落地失败”

当前代码最大的问题是：

**前后端协议、页面数据契约、告警模型、权限模型和任务同步细节，没有真正统一到 `PROJECT.md v1.5`。**

这导致项目出现大量“看起来已经有页面和接口，但实际跑不通或行为不符合规格”的问题。

### 3. 当前最严重的三类问题

1. 告警子系统处于半完成状态，存在直接运行失败的问题
2. Dashboard / Task Detail 的实时链路与接口契约大面积错位
3. 前端残留旧版模型和自造角色，导致与后端和文档明显分叉

---

## 三、合并后的高优先级问题

以下问题均为本次合并后保留的核心结论。

## A. 严重 Bug：运行时失败或核心功能不可用

### BUG-A01 告警服务仍在读取旧版字段，当前实现无法正常工作

### 涉及文件

1. `server/services/alert_service.py`
2. `server/models/task.py`

### 现象

`alert_service.py` 仍读取：

1. `task.alert_enabled`
2. `task.alert_metric`
3. `task.alert_operator`
4. `task.alert_threshold`

但当前 `ProbeTask` 模型实际定义的是：

1. `alert_latency_threshold`
2. `alert_loss_threshold`
3. `alert_fail_count`
4. `alert_eval_window`
5. `alert_trigger_count`
6. `alert_recovery_count`
7. `alert_cooldown_seconds`

### 结论

这不是小偏差，而是**字段模型已经变了，告警引擎还停留在旧版设计**。

结果是：

1. 告警评估会读到不存在字段
2. 外层虽然可能吞异常写日志
3. 但告警系统事实上不可认为已完成

### 修改意见

1. 按 v1.5 彻底重写告警评估逻辑
2. 以 `latency / packet_loss / continuous_fail` 三种规则分别评估
3. 禁止继续沿用单规则 `alert_metric + operator + threshold` 模式

---

### BUG-A02 告警历史写入和告警推送函数签名都与实际模型脱节

### 涉及文件

1. `server/services/alert_service.py`
2. `server/models/alert.py`
3. `server/ws/dashboard_handler.py`

### 现象

已确认两处直接不兼容：

1. `AlertHistory(...)` 构造时传入了 `operator=...`，但模型中没有这个字段
2. `push_alert(task_id, event_type, metric, actual_value)` 的调用方式，与 `push_alert(alert_data)` 的定义不一致

### 结论

即使告警评估进入触发路径，当前实现也会在：

1. 写告警历史
2. 推送 Dashboard 告警

这两步继续报错。

### 修改意见

1. `AlertHistory` 只传模型中真实存在的字段
2. 如果确实需要 `operator`，先统一模型、序列化、接口后再加
3. `push_alert` 统一成接收单一 payload dict 的形式

---

### BUG-A03 Webhook 通知读取的是不存在的配置字段，告警通道实际发不出去

### 涉及文件

1. `server/services/alert_service.py`
2. `server/models/alert.py`

### 现象

告警服务尝试从：

1. `channel.config_data`
2. `channel.config`

里解析 Webhook URL。

但当前 `AlertChannel` 模型实际只有：

1. `url`

### 结论

这意味着服务端通知逻辑和当前告警通道模型并不一致。

### 修改意见

1. 后端直接使用 `channel.url`
2. 不要再混用历史版 `config / config_data` 结构

---

### BUG-A04 历史补传数据没有做 60 秒外“只入库不告警”抑制

### 涉及文件

1. `server/ws/agent_handler.py`

### 现象

`on_agent_probe_result()` 在写入 InfluxDB 后，直接进入告警评估，没有基于 `timestamp` 判断是否为历史补传。

### 结论

这会导致断线补传数据也触发实时告警，形成：

1. 过期告警
2. 告警风暴
3. 状态失真

### 修改意见

1. 比较探测结果时间与当前时间差
2. 超过 60 秒只入库、ACK，不做告警评估
3. 批量补传路径也保持同样规则

---

### BUG-A05 `result_id` 去重只写在文档里，中心端没有真正执行

### 涉及文件

1. `server/services/influx_service.py`
2. `server/ws/agent_handler.py`
3. `agent/ws_client.py`

### 现象

Agent 已按规格生成 `result_id`，但中心端：

1. 没把 `result_id` 写入点数据
2. `check_result_exists()` 只是 stub，恒定返回 `False`
3. 写入前没有真正做幂等检查

### 结论

当前补传幂等性没有真正落地。

### 修改意见

1. 实现 `result_id` 的真实幂等检查
2. 不要把 Influx 的点覆盖特性当成业务去重替代品
3. 无论重复与否，都应正确返回 ACK

---

### BUG-A06 Dashboard 订阅与详情实时推送链路没有对齐，实时功能基本是断的

### 涉及文件

1. `server/ws/dashboard_handler.py`
2. `web/src/composables/useSocket.ts`
3. `web/src/views/TaskDetailView.vue`

### 现象

至少存在以下不一致：

1. 规格要求 `dashboard:subscribe_task` / `dashboard:unsubscribe_task`
2. 前端 emit 的是 `subscribe_task` / `unsubscribe_task`
3. 后端详情推送发的是 `dashboard:task_detail`
4. 前端监听的却是 `dashboard:task_update`
5. `connect_error` 前端仍然只读 `err.message`，没有按 v1.5 读取 `err.data.code`

### 结论

当前 Task Detail 的实时链路不能认为已打通。

### 修改意见

1. 订阅事件、详情推送事件、前端监听事件三方统一到 `PROJECT.md`
2. `connect_error` 改为按 `err.data.code` 做业务判断
3. 只保留一套正式 WebSocket 事件命名

---

### BUG-A07 Dashboard API 与前端 store / 页面字段契约完全错位

### 涉及文件

1. `server/api/data.py`
2. `web/src/api/data.ts`
3. `web/src/stores/dashboard.ts`
4. `web/src/views/DashboardView.vue`

### 现象

后端 `/api/data/dashboard` 返回：

1. `nodes`
2. `tasks`
3. `summary`

前端却按：

1. `{ cards: DashboardCard[] }`

来读，并直接使用：

1. `res.data.cards`

同时卡片字段命名也不一致。

### 结论

Dashboard 首页当前不是“字段少一点”，而是接口契约整体没对齐。

### 修改意见

1. 后端和前端先确定唯一正式结构
2. 如果保留 `cards`，后端直接输出 `cards`
3. 或者前端改成消费 `nodes/tasks/summary`
4. 四层统一：后端返回、前端 API、store、页面字段访问

---

### BUG-A08 Task Detail 页面当前基本不可用

### 涉及文件

1. `web/src/views/TaskDetailView.vue`
2. `web/src/api/data.ts`
3. `web/src/types/index.ts`

### 现象

已确认的问题包括：

1. 把 UUID 任务 ID 强转为 `Number`
2. 请求期望 `points`，后端返回的是 `data`
3. 页面读取 `p.time`，后端实际返回 `timestamp`
4. 实时监听事件名也不对

### 结论

任务详情页当前数据请求、图表字段和实时订阅三层都存在错位。

### 修改意见

1. Task ID 全链路改为字符串 UUID
2. 统一任务详情接口返回结构
3. 统一图表时间字段命名
4. 实时事件只保留规格中的正式命名

---

### BUG-A09 告警通道页面与后端 API 契约不一致，当前管理页不可认为可用

### 涉及文件

1. `web/src/api/alerts.ts`
2. `web/src/views/admin/AlertChannelsView.vue`
3. `web/src/types/index.ts`
4. `server/api/alerts.py`
5. `server/models/alert.py`

### 现象

已确认的不一致有：

1. 前端 `getAlertChannels()` 期待 `{ channels: [...] }`，后端返回 `{ items: [...] }`
2. 前端类型和页面使用 `config.url`
3. 后端实际模型和接口使用扁平 `url`
4. 前端创建/更新发送的是 `config: { url }`
5. 后端读取的是 `data.get('url')`

### 结论

告警通道管理页当前前后端并不在同一套数据结构上。

### 修改意见

1. 推荐统一为扁平 `url` 字段
2. 前端 API、类型、页面表单全部改成与后端一致
3. 列表响应结构也同步统一

---

### BUG-A10 任务管理页仍在使用旧版任务/告警模型

### 涉及文件

1. `web/src/views/admin/TasksView.vue`
2. `web/src/types/index.ts`
3. `server/api/tasks.py`
4. `server/models/task.py`

### 现象

页面和类型仍保留：

1. `alert_enabled`
2. `alert_metric`
3. `alert_operator`
4. `alert_threshold`
5. `target_type = node | external`

但当前规格和后端实际模型是：

1. `alert_latency_threshold`
2. `alert_loss_threshold`
3. `alert_fail_count`
4. `target_type = internal | external`

另外：

1. 前端切换启停时没有给 `/toggle` 接口传 `enabled`
2. 后端明确要求请求体必须包含 `enabled`

### 结论

任务管理页当前仍是旧版实现残留，不可认为已符合最终规格。

### 修改意见

1. 按 v1.5 重新设计任务表单
2. 告警配置拆分为三类阈值
3. `target_type` 统一改为 `internal / external`
4. 启停接口补齐 `enabled` 请求体

---

### BUG-A11 节点部署命令链路断裂

### 涉及文件

1. `server/api/nodes.py`
2. `server/api/__init__.py`
3. `web/src/api/nodes.ts`
4. `web/src/views/admin/NodesView.vue`
5. `scripts/install-agent.sh`

### 现象

已确认两层问题：

1. 后端返回的是 `script_command` / `docker_command`，前端却读取 `res.data.command`
2. 仓库有 `scripts/install-agent.sh`，但当前后端没有实际暴露 `/api/install-agent.sh` 路由

### 结论

当前节点部署命令功能链路没有闭环。

### 修改意见

1. 前端分别展示脚本安装命令和 Docker 命令
2. 后端补 `/api/install-agent.sh` 路由，或修改部署方式，不要引用不存在的下载入口

---

### BUG-A12 前端引入了文档不存在的 `operator` 角色，权限模型已漂移

### 涉及文件

1. `web/src/types/index.ts`
2. `web/src/stores/auth.ts`
3. `web/src/router/index.ts`
4. `web/src/views/admin/UsersView.vue`
5. `server/models/user.py`
6. `server/api/users.py`

### 现象

当前 `PROJECT.md v1.5` 只定义：

1. `admin`
2. `readonly`

但前端仍保留：

1. `operator`
2. `requiresOperator`
3. “操作员”角色选项

后端却只接受 `admin / readonly`。

### 结论

这是典型的前端权限模型漂移。

### 修改意见

1. 如果以当前文档为准，就彻底删除 `operator`
2. 路由守卫、类型、用户管理页统一回到两角色模型

---

### BUG-A13 UUID 类型和分页结构在多个管理页里都写错了

### 涉及文件

1. `web/src/types/index.ts`
2. `web/src/api/tasks.ts`
3. `web/src/api/users.ts`
4. `web/src/api/alerts.ts`
5. `web/src/views/admin/NodesView.vue`
6. `web/src/views/admin/TasksView.vue`
7. `web/src/views/admin/UsersView.vue`

### 现象

前端类型把多个 UUID 主键定义成了 number，例如：

1. `User.id`
2. `ProbeTask.id`
3. `AlertChannel.id`
4. `AlertHistory.task_id`

同时多个列表页按：

1. `res.data.total`

读取分页总数，但后端实际统一返回：

1. `items`
2. `pagination: { total, ... }`

### 结论

这是全站性的前端类型和分页协议问题。

### 修改意见

1. 把所有 UUID 主键统一改成字符串
2. 定义正确的分页响应类型
3. 所有列表页统一读取 `pagination.total`

---

## B. 与规格不一致或高风险的实现偏差

### BUG-B01 任务同步状态机只写了 ACK 片段，没有真正实现 pending / desync / 重试

### 涉及文件

1. `server/ws/agent_handler.py`
2. `server/services/task_service.py`

### 现象

代码里虽然有 `_task_ack_pending = {}`，但实际没有：

1. 把待确认版本真正纳入 pending 管理
2. 超时重试
3. 最大重试次数
4. desync 标记
5. 与重连强制全量同步联动

### 结论

当前任务同步只实现了“发消息”和“收到 ACK 后清理”的片段，没有真正实现 `PROJECT.md` 里的状态机。

### 修改意见

1. 补 pending -> synced / desync 状态流转
2. 补 30 秒超时重发和最多 3 次规则
3. desync 后节点重连时强制全量 `center:task_sync`

---

### BUG-B02 Dashboard 搜索与默认排序没有完整按规格实现

### 涉及文件

1. `server/api/data.py`

### 现象

当前搜索只匹配任务名，没有完整覆盖：

1. 节点名
2. 目标地址

默认排序也只是简单按名称排序，没有真正实现“告警任务置顶”。

### 结论

Dashboard API 当前属于“能返回数据，但行为还没达到规格”的状态。

### 修改意见

1. 搜索补齐任务名 / 节点名 / 目标地址匹配
2. 默认排序补 alert_status 优先规则

---

### BUG-B03 探测结果提交未验证任务归属节点，存在数据污染风险

### 涉及文件

1. `server/ws/agent_handler.py`

### 现象

当前中心端根据连接已认证出 `node_id`，但在写入探测结果前，没有验证：

1. `task.source_node_id == 当前连接节点`

### 结论

理论上已认证节点可以上报不属于自己的任务结果，造成数据污染。

### 修改意见

1. 在写入前强制校验 `task.source_node_id`
2. 不属于当前节点的任务结果应拒绝处理，但仍可 ACK 以避免死循环重传

---

### BUG-B04 Docker 启动方式与 eventlet 模式不匹配

### 涉及文件

1. `server/extensions.py`
2. `Dockerfile`

### 现象

项目把 Socket.IO 配置为 `async_mode='eventlet'`，但 Docker 启动命令却是 Flask 开发服务器：

1. `python -m flask ... run`

### 结论

这不是理想的生产 WebSocket 启动方式，存在稳定性和部署偏差风险。

### 修改意见

1. 改为 gunicorn + eventlet worker
2. 或使用 `socketio.run()` 的正式启动入口

---

### BUG-B05 心跳每秒写 SQLite，会放大写入压力

### 涉及文件

1. `server/ws/agent_handler.py`
2. `server/services/node_service.py`

### 现象

Agent 每秒发一次心跳，而服务端在 `on_agent_heartbeat()` 里每次都更新：

1. `node.last_seen`
2. `db.session.commit()`

### 结论

随着节点数增加，这会给 SQLite 带来持续写压力。

### 修改意见

1. 心跳处理只更新内存窗口
2. 由后台任务批量刷新 `last_seen`

---

## 四、这次合并时剔除的结论

以下是三份来源中出现过、但**本次没有保留进最终问题清单**的项：

### 1. InfluxDB Measurement 名称应为 `probe_results`

本次核查当前 `project-files/PROJECT.md v1.5` 后，文档 6.1 节明确写的是：

1. `probe_result`

因此，“代码使用单数而规格要求复数”这一条**不适用于当前版本规格**，应视为旧报告上下文残留，本次不纳入最终问题。

---

## 五、统一修复顺序

### 第一阶段：先让核心链路能跑通

1. 重写告警服务字段模型
2. 修复告警历史写入和 `push_alert` 调用
3. 修复 Webhook URL 读取
4. 补历史补传数据告警抑制

### 第二阶段：统一前后端接口契约

5. 修复 Dashboard API 与前端 store / 页面结构
6. 修复 Task Detail 页 UUID、字段名、实时事件
7. 修复 Alert Channels 页面与后端契约
8. 修复 Nodes 部署命令返回结构和脚本暴露链路
9. 修复 UUID / 分页类型问题

### 第三阶段：收回规格漂移

10. 重做任务管理页，回到 v1.5 的任务/告警模型
11. 删除前端 `operator` 角色残留
12. 统一 Dashboard / Task Detail 的 WebSocket 命名

### 第四阶段：补协议完整性与运行质量

13. 实现 `result_id` 去重
14. 实现 task sync 的 pending / desync / retry 状态机
15. 校验 task 归属节点身份
16. 调整 Docker 启动方式
17. 优化心跳数据库写入频率

---

## 六、最终结论

这三份报告合并后的稳定结论是：

1. 项目没有偏离 NetworkStatus-Rabbit 的产品主题
2. 当前最严重的问题不是“方向错”，而是“规格与实现没有真正收口”
3. 告警、WebSocket、前后端接口契约、任务管理页、告警通道页，是当前问题最集中的区域

如果现在直接继续叠功能，而不先做这一轮收口，项目会继续出现：

1. 页面看似齐全但交互不可用
2. WebSocket 看似接通但事件根本不对齐
3. 告警看似有代码但实际上不可靠

这份 `gpt5.4-bug-rep.md` 可以作为下一轮集中修复的统一基线。

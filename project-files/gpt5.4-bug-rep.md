# NetworkStatus-Rabbit Bug Report

任务名称：debug NetworkStatus-Rabbit

当前文档版本：v0.125

最后整理时间：2026-03-24

文档原则：

1. 当前状态里只保留未解决问题。
2. 每个问题都必须包含代码依据和可执行的实现思路。
3. 已解决内容只放在对应版本的“已完成任务”中，不再回放全文。

---

## 1. 当前状态

### v0.125 当前问题

1. `icmp` 改成单次探测后，抖动字段在当前实现里被直接做没了，详情页自然不会再显示抖动。
现象：你给的截图里 `icmp` 延迟波动非常明显，但详情页抖动指标消失了。这不是图表没画，而是后端已经不给抖动值了。
代码依据：
1. [agent/probes/icmp_probe.py](agent/probes/icmp_probe.py) 当前 `probe()` 已经被改成 `count = 1`，每轮只发 1 个 echo request。
2. 同文件的 `_parse_jitter()` 只会解析 Linux `ping` 多包输出里的 `mdev`，正则目标是 `rtt min/avg/max/mdev = ...`。单次 ping 不会产生这段统计，Windows 也没有对应分支，所以当前实现下 `jitter` 基本恒为 `None`。
3. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 只有在 `points` 里存在非空 `jitter` 时才会追加“抖动 (ms)”序列；因此上游一旦全是 `None`，前端就会像“抖动功能消失”一样。
4. [project-files/PROJECT.md](project-files/PROJECT.md) 的 6.1 和 10.4 明确把 `jitter` 定义为 `icmp` 指标之一，详情页也明确要求 `ICMP Ping` 展示抖动折线图。
实现思路：
1. 既然 `icmp` 现在采用“单次调度 = 一条基础样本”，抖动就不能再依赖操作系统 ping 的多包汇总输出，而应改成基于最近 N 条 `latency` 在窗口内计算，例如服务端 rolling jitter 或前端窗口内抖动。
2. 如果继续在 agent 端出 `jitter`，也必须由 agent 自己维护每个任务最近若干次 `latency` 的滑动窗口，再把窗口计算结果塞进当前样本，而不是继续从单条 ping 输出里硬解析。
3. 在新计算逻辑上线前，前端至少应明确区分“当前协议无抖动字段”和“抖动值暂不可用”，避免用户误判为链路稳定。
决定方向：按 Project 的展示语义和你这轮确认，`icmp jitter` 一律由前端基于最近 10 个 `latency` 点计算，不在 agent 单条样本里产出 `jitter`。前端必须把该值明确定义为“窗口抖动”，并在 tooltip 与统计卡中统一使用同一套 10 点窗口结果。
影响：目前 `icmp` 的抖动图和抖动语义实际失效，用户会被误导成“只有延迟，没有抖动”。
验收标准：`icmp` 任务在存在延迟波动时，详情页能够稳定显示抖动值和抖动曲线；不能再因为单次 ping 模式而把抖动整项做没。

2. Agent 当前并没有按 Project 11.4 集成 Network-Monitoring-Tools-web 作为探测核心，现有多协议实现是简化自写版本，`udp` 问题只是最明显的外显症状。
现象：你指出的 `udp 4ms`、无丢包、无抖动只是当前探测核心偏离 Project 的直接结果之一。继续往下检查后，已经可以确认目前 agent 并没有按工程文档把 Network-Monitoring-Tools-web 放进 `agent/network_tools/` 作为底层探测核心。
代码依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.4 明确写死：`agent/` 下应存在 `network_tools/` 目录，`probes/*.py` 只是适配层，用来包装 Network-Monitoring-Tools 的原始实现。
2. 实际目录 [agent](agent) 下只有 `config.py`、`local_cache.py`、`main.py`、`probes/`、`scheduler.py`、`ws_client.py`，不存在 Project 里要求的 [agent/network_tools](agent) 这一层原始探测代码目录。
3. [agent/probes/__init__.py](agent/probes/__init__.py) 只是直接导入当前自写的 `icmp_probe.py`、`tcp_probe.py`、`udp_probe.py`、`http_probe.py`、`dns_probe.py`，没有任何对 Network-Monitoring-Tools-web 的包装入口。
4. [agent/main.py](agent/main.py) 启动链路里也只会初始化本仓库自己的 probe registry，没有加载外部 network tools 代码。
5. [requirements-agent.txt](requirements-agent.txt) 中也看不到任何为 Network-Monitoring-Tools-web 集成准备的本地包/模块依赖，说明当前 agent 运行时并未把那套工具当作第一探测核心。
6. 最直接的协议偏差体现在 [agent/probes/udp_probe.py](agent/probes/udp_probe.py)：它当前只是执行 `nc -u -z -w timeout target port`，然后把命令耗时当成 `latency`，并且完全不返回 `packet_loss` / `jitter`。这与外部仓库文档中 UDP 客户端“发送多包、接收回显、计算 RTT/丢包/抖动”的定义完全不同。
7. 从外部文档与源码可见，`wingsrabbit/Network-Monitoring-Tools-web` 的 UDP 工具明确提供服务端/客户端模型，以及批量 RTT、丢包、抖动计算，不是当前这个 `nc` 检查模式。
实现思路：
1. 需要先把“探测核心”这件事定死：是继续维护当前这套简化 probe，还是回到 Project 规定的 Network-Monitoring-Tools-web 包装模式。
2. 如果按 Project 走，`agent/network_tools/` 应补齐并作为正式底层；`icmp/tcp/udp/http/dns` 的 `*_probe.py` 只负责参数适配和结果归一化。
3. `udp` 应优先迁回外部工具的 client/server 回显模型，否则就算前端补图，指标仍然没有物理意义。
4. 在正式迁回之前，当前 `udp` 至少应从“可信监测协议”降级为“实验性/未达标实现”，避免继续误导判断。
决定方向：以 Project 11.4 为准，Agent 必须补齐 `agent/network_tools/` 并以 Network-Monitoring-Tools-web 作为正式探测核心；当前自写 `probes/*.py` 只允许作为适配层，不允许继续承担实际探测核心职责。UDP 协议必须回到外部工具定义的 client/server 回显测量模型，不再允许使用 `nc -u -z` 作为正式实现。
影响：这不是单一 UDP bug，而是 agent 探测层整体实现偏离工程文档，后续任何协议指标都可能继续出现“看起来有数，实际语义不对”的问题。
验收标准：仓库结构、agent 启动链路、各协议 probe 的实现方式与 Project 11.4 一致；特别是 UDP 必须回到可计算 RTT/丢包/抖动的真实探测模型。

3. 任务编辑接口存在“先提交数据库，再做后续动作”的事务边界错误，导致接口报错时数据可能已经部分落库。
现象：你在编辑任务时会收到“服务器内部错误”，操作看起来失败；但刷新后台后，面板又显示某些内容已经变更。这说明“响应失败”和“数据是否已写入”当前不是同一个结果。
代码依据：
1. [server/api/tasks.py](server/api/tasks.py) 的 `update_task()` 先把 `task` 字段写进 SQLAlchemy session，然后调用 `task_service.increment_config_version(task.source_node_id)`。
2. [server/services/task_service.py](server/services/task_service.py) 的 `increment_config_version()` 内部自己执行了一次 `db.session.commit()`。由于它和 `update_task()` 共用同一个 session，这次 commit 会把当前任务修改一并提前落库。
3. `update_task()` 在这之后还会继续执行 `_notify_agent_task_change(...)`。如果通知阶段抛异常，接口就会返回 500，但数据库里的任务修改已经被前面的 commit 提交了。
4. 同样的结构也出现在 [server/api/tasks.py](server/api/tasks.py) 的 `create_task()`、`delete_task()`、`toggle_task()`，都存在“持久化与后续动作不在同一事务语义里”的风险。
实现思路：
1. `increment_config_version()` 不应在 service 内部偷偷 commit；它应只修改 node 对象，把事务提交权交回调用方。
2. `tasks.py` 应把“任务变更 + config_version 递增”作为一次明确的数据库事务处理，成功后再做 websocket 通知；通知失败也不应伪装成数据库失败，而应返回“保存成功但下发失败/待重试”的明确信号。
3. 如果坚持在通知失败时返回错误，也必须在响应语义上明确这是“下发失败”而不是“保存失败”，否则前端必然误判。
决定方向：以 Project 的状态机和同步语义为准，任务编辑接口必须把“数据库保存成功”和“agent 下发成功”拆成两个明确状态。HTTP 响应主语义只表达数据库保存是否成功；若下发失败，响应中必须返回明确的 `sync_pending` 或 `sync_failed` 状态，不再允许使用 500 混淆为“保存失败”。
影响：现在的错误提示不可信，用户看到 500 并不能判断到底是没保存、部分保存，还是保存成功但同步失败。
验收标准：编辑接口返回失败时，前后端对“数据有没有落库”必须有一致语义；不能再出现“接口报错但刷新后已改”的情况。

4. 任务编辑前后端契约不一致，前端允许修改一批字段，但后端更新接口实际上只会保存其中一小部分。
现象：编辑弹窗里可以修改源节点、协议、目标类型、目标地址、目标节点等核心字段，但当前后端 `PUT /tasks/<id>` 并不会真正更新这些字段。用户从 UI 视角看是在“编辑整个任务”，从后端视角看却只是“改一小部分字段”。
代码依据：
1. [web/src/views/admin/TasksView.vue](web/src/views/admin/TasksView.vue) 的编辑弹窗会把整个 `task` 拷进 `form`，并允许修改 `source_node_id`、`protocol`、`target_type`、`target_node_id`、`target_address`、`target_port`、`interval`、`timeout` 等完整字段集。
2. 但 [server/api/tasks.py](server/api/tasks.py) 的 `update_task()` 实际只处理 `interval`，以及 `name`、`timeout`、`target_port` 和各类告警字段。它不会更新 `source_node_id`、`protocol`、`target_type`、`target_node_id`、`target_address`。
3. 这意味着即使接口返回 200，用户对这些核心字段的修改也可能根本没落库；而当它与上一个问题叠加时，就会出现更混乱的“部分字段变了、部分字段没变、响应还报错”的体验。
实现思路：
1. 要么把后端更新接口补齐成真正支持这些字段的完整编辑，并补充对应校验和 agent 重下发逻辑。
2. 要么前端在编辑模式里把这些不支持变更的字段明确禁用，只允许修改当前后端真正支持的字段。
3. 无论选哪条路，都必须把“可编辑字段集合”写死在前后端同一份契约里，不能再由前端自行猜测。
决定方向：以当前 Project 和现有后端能力为准，前端编辑页必须立即禁用所有后端 `PUT /tasks/<id>` 未支持的字段，只保留 `name`、`interval`、`timeout`、`target_port` 与告警参数可编辑。任何未被后端正式支持的字段，不允许继续显示为可编辑状态。
影响：当前管理页不是单纯的 UI bug，而是接口能力边界没锁死，AI 和人工都会被误导。
验收标准：编辑页面里能改的字段，后端就必须真实支持；后端不支持的字段，前端不能再给出可编辑假象。

---

## 2. 已完成任务

### v0.12 已完成

本版本已完成的事项：

1. 统一前端数值显示规范，延迟与抖动按两位小数显示，避免出现过长浮点数或 `0.0 ms` 这类误导性结果。
2. 统计卡与图表更新逻辑对齐，避免“图表在动、顶部统计不动”的割裂现象。
3. `7 天 / 30 天` 视图不再直接混入秒级实时点，长周期视图与原始秒级视图完成分离。
4. tooltip、统计卡、首页延迟显示的精度规则统一，不再同一份数据出现多套展示标准。
5. 长周期视图的数据粒度语义完成梳理，明确 `7 天` 为分钟级、`30 天` 为小时级。

验收结果：已完成，后续不再作为“现状问题”重复列出。

### v0.121 已完成

本版本已完成的事项：

1. 页面底部增加全局状态栏，支持显示 `Powered by NetworkStatus-Rabbit`、GMT+8 当前时间和最后更新时间状态。
2. `最后更新` 的显示规则明确，小于 10 秒统一视为 `10秒内`。
3. `7 天 / 30 天` 视图在不混入秒级实时点的前提下补足自动更新能力，不再需要手动切换或刷新页面。
4. `30 分钟 ~ 24 小时` 在历史不足时允许保留空白区，明确展示数据实际开始记录的时间，而不是把已有数据拉伸铺满整张图。
5. 原始时间窗口与图表横轴语义对齐，避免出现“选择 1 小时但起始时间仍不断滑动、看起来永远被困在当前一段数据里”的误解。
6. 图表已补充 `dataZoom` 缩放能力，支持进入局部详细视图。
7. 页面已补充“重置缩放”按钮，可从局部详细视图返回基础视图。

验收结果：已完成，后续不再作为“现状问题”重复列出。

### v0.122 已完成

本版本已完成的事项：

1. 报告结构从“长篇堆叠问题清单”收敛为“当前状态 / 已完成任务”两段式，避免已解决问题持续污染现状判断。
2. 问题项写法统一成“现象、代码依据、实现思路”的固定结构，不再保留泛化建议或模板化废话。
3. 当前版本只保留未解决问题，已确认完成的历史问题不再重复回放全文。

验收结果：已完成，后续继续沿用该文档组织方式。

### v0.123 已完成

本版本已完成的事项：

1. 后端 [server/api/data.py](server/api/data.py) 的任务统计接口已补充 `interval_seconds`、`window_start`、`window_end`、`expected_probes`，为理论点数和窗口语义提供基础元数据。
2. 前端 [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 已开始展示 `实际记录数 / 理论记录数` 的基础形态，不再只显示单一 `total_probes`。
3. Agent 调度器 [agent/scheduler.py](agent/scheduler.py) 已切换为固定节拍模型，不再是旧版“探测完成后再 sleep interval”的串行漂移写法。
4. `v0.123` 对应的当前问题已经完成一次代码复查，旧判断中“调度器是唯一主因”的表述已被修正，不再作为现状结论继续保留。

验收结果：已完成，后续在此基础上继续追查协议实现和窗口语义问题。

---



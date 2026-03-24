# NetworkStatus-Rabbit Bug Report

任务名称：debug NetworkStatus-Rabbit

当前文档版本：v0.127

最后整理时间：2026-03-24

当前审查基线：

1. NetworkStatus-Rabbit 本地审查分支：`NetworkStatus-Rabbit-NG`
2. Network-Monitoring-Tools 本地对照路径：`D:\wingsrabbit-ovo\Network-Monitoring-Tools`

文档原则：

1. 当前状态里只保留未解决问题。
2. 每个问题都必须包含代码依据和可执行的实现思路。
3. 已解决内容只放在对应版本的“已完成任务”中，不再回放全文。

---

## 1. 当前状态

### v0.127 当前问题

1. 整个探测核心仍未按 Project 11.4 真正接入本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`，当前仓库只是用自写代码占位了 `network_tools/` 目录。
现象：仓库表面上已经有 `agent/network_tools/`，但继续深查后可以确认，这里并不是本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的原始实现，而是本仓库自写的简化探测代码。也就是说，当前项目在“目录名”上对齐了 Project，在“实现来源”上没有对齐。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 1.3 明确写死：Network-Monitoring-Tools 作为底层探测模块直接集成。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.4 明确写死：`probes/*.py` 是适配器，真正的探测核心应放在 `agent/network_tools/`，由适配层包装其能力。
代码依据：
1. [agent/network_tools/icmp_ping/__init__.py](agent/network_tools/icmp_ping/__init__.py) 仍然是本仓库自写的 `subprocess + ping` 解析实现，不是上游项目代码。
2. [agent/network_tools/udp_ping/__init__.py](agent/network_tools/udp_ping/__init__.py) 仍然是本仓库自写的 `socket` 批量发送/接收实现，不是上游项目代码。
3. [agent/probes/icmp_probe.py](agent/probes/icmp_probe.py)、[agent/probes/tcp_probe.py](agent/probes/tcp_probe.py)、[agent/probes/udp_probe.py](agent/probes/udp_probe.py) 只是包装本仓库自己的 `agent.network_tools.*`，并没有包装外部仓库原始实现。
4. [agent/probes/http_probe.py](agent/probes/http_probe.py) 与 [agent/probes/dns_probe.py](agent/probes/dns_probe.py) 甚至连 `agent/network_tools/` 都没走，仍然直接调用 `curl/requests/nslookup`。
5. [requirements-agent.txt](requirements-agent.txt) 中没有任何用于引入上游探测核心的依赖，进一步说明当前不是“真实集成”，而是“本地重写”。
实现思路：
1. 必须先把探测核心的来源锁死，不允许继续用“目录名相同”替代“实现来源一致”。
2. `agent/network_tools/` 必须替换成真实的本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 原始探测代码，`probes/*.py` 只负责参数适配与结果归一化。
3. HTTP、DNS 也必须和 ICMP/TCP/UDP 一样，统一走 `network_tools/` 底层，不允许继续直接散落在适配层里各自调用系统命令。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 为准，`agent/network_tools/` 必须承载来自本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的真实探测核心；`agent/probes/*.py` 只允许做适配层，不允许继续直接承担探测实现。
影响：如果这一层不纠正，后续所有协议行为都可能继续出现“名字对了、结果不一定对、规格也对不上”的问题，整个探测体系没有可信的基线。
验收标准：`agent/network_tools/` 中的实现来源与 Project 规定一致；五类协议的实际探测入口都统一收敛到该目录，再由 `probes/*.py` 包装导出。

2. C/S 探测组件没有统一落在本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 体系下，尤其 UDP 与 HTTP/DNS 的实现路径仍然偏离 Project 要求。
现象：用户要求“所有 C/S 的测试组件必须使用 Network-Monitoring-Tools”，但当前实现里只有 ICMP/TCP/UDP 名义上走了本地 `network_tools/`，HTTP 与 DNS 仍然直接在 probe 层调用系统工具；同时 UDP 也不是明确对齐本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 那套 C/S 组件，而是本仓库自己的实现。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.4 把探测核心设计成统一的 `network_tools/ + probes adapter` 两层结构。
2. 用户补充约束已经进一步写死：所有 C/S 测试组件必须使用 Network-Monitoring-Tools。
代码依据：
1. [agent/probes/http_probe.py](agent/probes/http_probe.py) 直接使用 `curl` 或 `requests`，没有接入任何 `network_tools/curl_ping`。
2. [agent/probes/dns_probe.py](agent/probes/dns_probe.py) 直接使用 `nslookup`，没有接入任何 `network_tools/dns_lookup`。
3. [agent/network_tools/udp_ping/__init__.py](agent/network_tools/udp_ping/__init__.py) 虽然能返回 RTT、丢包、抖动，但它仍然是本仓库自写实现，不是 Project 规定的上游探测核心，也不能证明当前 C/S 组件与外部工具仓库保持一致。
实现思路：
1. 所有协议必须统一进入同一条探测架构：`network_tools/` 负责原始测量，`probes/` 负责适配结果。
2. HTTP 必须补齐 `network_tools/curl_ping` 入口，DNS 必须补齐 `network_tools/dns_lookup` 入口，不允许继续把系统命令直接塞在 `probes/` 层。
3. UDP 必须明确对齐到本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 定义的那套 C/S 组件与统计语义，不能只在“字段看起来像”这一层自证合规。
决定方向：所有 C/S 测试组件一律统一收敛到 `agent/network_tools/`，并以本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 代码为唯一底层实现来源；`probes/` 层不再允许直接发起真实测量。
影响：当前协议层实现路径分裂，AI 或人工继续维护时会不断碰到“有的协议走底层模块，有的协议直接跑命令”的结构性混乱。
验收标准：五类协议的真实测量逻辑全部下沉到 `agent/network_tools/`，`probes/` 层只保留适配，不再出现 `curl/requests/nslookup` 直接出现在 probe 适配层的情况。

3. 任务同步状态机没有按 Project 在任务变更时进入 `pending`，当前只有全量同步路径会标记 `pending`。
现象：Project 明确写了任务同步状态机：创建/修改/删除任务后，节点应进入 `pending`，等待 `agent:task_ack`，超时则重试，重试失败转 `desync`。但当前代码里，`pending` 只在 agent 重连后的全量 `task_sync` 路径触发，日常的任务增删改并没有把同步状态机真正驱动起来。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.6 规定了 `config_version` 驱动的同步机制。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 8.3 明确状态机：`synced -> pending -> synced/desync`，且 `pending` 超时需要重试。
代码依据：
1. [server/services/task_service.py](server/services/task_service.py) 虽然定义了 `mark_sync_pending()`、`mark_sync_acked()`、`check_pending_syncs()`，但任务变更接口并没有使用这套状态机入口。
2. [server/api/tasks.py](server/api/tasks.py) 的 `create_task()`、`update_task()`、`delete_task()`、`toggle_task()` 都只做了 `config_version` 递增、提交数据库、尝试 websocket 下发，没有调用 `task_service.mark_sync_pending()`。
3. [server/ws/agent_handler.py](server/ws/agent_handler.py) 中 `task_service.mark_sync_pending()` 只出现在 agent 连接后的 `center_task_sync` 全量同步路径里。
实现思路：
1. 任务增删改一旦导致 `config_version` 变化，就必须同步进入 `pending` 状态。
2. websocket 下发后必须等待 `agent:task_ack` 驱动回 `synced`；超时必须走 `check_pending_syncs()` 定义的重试/降级路径。
3. 前端返回的 `sync_status` 不能只是装饰字段，而必须真实绑定这套状态机。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.6 与 8.3 为准，所有任务变更接口在成功写库并发出变更事件后，必须立即调用 `mark_sync_pending()`；后续 ACK、超时重试、降级 `desync` 一律走既有状态机实现，不允许继续只增版本号、不驱动状态机。
影响：如果这条链路不补齐，当前所谓 `sync_status`、`config_version`、`desync` 只是半套实现，无法真正反映 agent 是否拿到了最新任务。
验收标准：任意任务创建、修改、删除、启停后，对应节点都能进入 `pending`；收到 ACK 回到 `synced`；超时后进入重试与 `desync` 流程。

4. 节点管理页没有按 Project 10.6 展示协议支持状态。
现象：Project 明确要求节点管理页展示每个节点支持哪些协议，绿色表示支持，灰色表示不支持，并与 Agent 的 capabilities 联动。当前节点管理页仍然只展示名称、状态、标签、版本和 IP，看不到任何协议支持状态。
Project 依据：[project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 明确写死：节点列表必须展示协议支持状态（绿色=支持 / 灰色=不支持），与能力发现联动。
代码依据：
1. [web/src/views/admin/NodesView.vue](web/src/views/admin/NodesView.vue) 当前列定义只包含 `ID / 名称 / 状态 / 启用 / 标签 / 版本 / IP / 操作`。
2. 同文件没有任何一列读取 `node.capabilities`，也没有协议状态 tag 渲染逻辑。
实现思路：
1. 节点列表必须新增“协议支持”列。
2. 该列必须读取节点的 `capabilities.protocols` 与 `unsupported/unsupported_reasons`，按协议逐项渲染支持状态。
3. UI 层必须严格按 Project 使用绿色/灰色标签，并在不支持时展示原因提示。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 为准，节点管理页必须新增协议支持状态展示，不允许继续省略 `capabilities` 的前端可视化。
影响：当前能力发现虽然上报了，但管理员在 UI 上看不到结果，等同于能力发现只做了半套。
验收标准：节点管理页可直接看到每个节点对 ICMP/TCP/UDP/HTTP/DNS 的支持状态，并能查看不支持原因。

5. 任务管理页创建任务时没有按 Project 10.6 做协议兼容性检查提示。
现象：Project 明确要求“创建任务时检查源节点协议支持，不阻止创建，但要给提示”。当前任务管理页虽然会加载节点列表，但在创建任务时完全没有利用节点 capabilities 做兼容性检查。
Project 依据：[project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 明确写死：管理员创建任务时，如果源节点不支持所选协议，前端应显示警告提示。
代码依据：
1. [web/src/views/admin/TasksView.vue](web/src/views/admin/TasksView.vue) 会通过 `getNodes()` 拉取节点列表，但 `nodeOptions` 只拿了节点 `name + id`。
2. 同文件的 `handleSubmit()` 只校验必填字段，没有任何“源节点 capabilities 是否支持当前 protocol”的检查逻辑。
3. 创建表单也没有 warning、badge、tip 或禁用/提示 UI。
实现思路：
1. 任务创建表单必须把节点 capabilities 带入本地状态。
2. 当 `source_node_id` 或 `protocol` 改变时，前端必须立即判断是否兼容。
3. 若不兼容，前端必须给出明确 warning，但不阻止提交，以符合 Project 原文。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 为准，任务创建页必须在源节点或协议变化时立即执行兼容性检查，并在不支持时显示 warning 提示；该提示不阻止创建，但不得缺失。
影响：当前管理员只能靠猜测节点支持哪些协议，容易创建出一批从一开始就不可执行的任务。
验收标准：创建任务时，界面能实时显示“当前源节点是否支持所选协议”；不支持时有清晰 warning，但仍允许管理员自行决定是否创建。

6. Dashboard 详情订阅协议与 WebSocket 错误语义没有按 Project 7.8 与 7.9 原样落地，当前实现仍停留在“能跑通一条私有命名”而不是“按规格实现协议面”。
现象：Project 已经把详情页订阅事件名、握手失败读取方式、连接后错误码行为全部写死，但当前前后端都在使用下划线私有事件名，且前端只打印 `connect_error`，没有按 Project 执行登录跳转或订阅异常处理。也就是说，当前代码不是“规格实现”，而是“前后端私下约定后自洽”。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.8 明确写死：详情页事件名应为 `dashboard:subscribe_task`、`dashboard:unsubscribe_task`、`dashboard:task_detail`。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.9 明确写死：握手拒绝走 `connect_error`，前端统一从 `err.data.code` 读取错误码；连接建立后的权限、订阅、参数错误必须通过 `error` 事件下发，并按错误类型执行对应处理。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单明确要求订阅发送/取消订阅、无效订阅错误、握手鉴权失败等场景都可被逐项验证。
代码依据：
1. [web/src/composables/useSocket.ts](web/src/composables/useSocket.ts) 里 `subscribeTask()` / `unsubscribeTask()` 发送的是 `dashboard_subscribe_task` / `dashboard_unsubscribe_task`，不是 Project 写死的冒号事件名。
2. [server/ws/dashboard_handler.py](server/ws/dashboard_handler.py) 里实际处理函数也是 `on_dashboard_subscribe_task()` / `on_dashboard_unsubscribe_task()`，说明服务端协议面同样没有按 Project 命名实现。
3. [web/src/composables/useSocket.ts](web/src/composables/useSocket.ts) 对 `connect_error` 只做 `console.error`，没有按 7.9 要求在 `WS_AUTH_FAILED` 下跳转登录，也没有统一处理 `WS_INVALID_SUBSCRIBE` / `WS_BAD_REQUEST` 等错误事件。
4. [server/ws/dashboard_handler.py](server/ws/dashboard_handler.py) 当前只覆盖了 `WS_AUTH_FAILED`、`WS_INVALID_SUBSCRIBE`、`WS_BAD_REQUEST`，没有实现 Project 7.9 中写死的 `WS_TOKEN_EXPIRED` 延迟断开流程，也没有明确的权限错误分支。
实现思路：
1. Dashboard 命名空间的事件名必须统一切回 Project 定义的冒号命名，不允许继续使用下划线私有协议。
2. 前端必须建立统一 WS 错误处理层：`connect_error` 处理握手失败，`error` 事件处理已连接状态下的订阅错误、权限错误、Token 过期。
3. 详情页进入/离开和异常订阅场景必须能按 Project 17 的自测项逐条跑通。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.8、7.9、17 为准，Dashboard 订阅协议与错误语义必须原样落地；前后端不得继续自定义一套下划线事件名和“只打印日志不处理”的弱实现。
影响：如果协议面继续漂移，后续 AI 或人工会同时维护两套“文档协议”和“代码协议”，细节页订阅、鉴权失败和异常处理都会继续失真。
验收标准：前后端统一使用 Project 定义的事件名；`connect_error`、`WS_INVALID_SUBSCRIBE`、`WS_BAD_REQUEST`、`WS_TOKEN_EXPIRED` 均能按 Project 规定的方式被前端识别和处理。

7. 能力发现的 UDP 自检标准没有按 Project 11.5 落地，当前 Agent 把“能创建 Python UDP socket”当成了“支持 UDP Ping”，与规格写死的依赖检查不一致。
现象：Project 对 UDP 自检写得很死，要求检查 `nc` 是否存在，因为能力发现本身要反映底层探测能力是否可用；但当前代码直接用 Python `socket` 建一个 UDP socket 就返回成功，这会把“环境不具备 Project 规定的 UDP 依赖”误报成“协议支持”。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.5 明确写死：UDP Ping 自检方式是检查 `nc`（netcat）命令是否存在，判定标准是 `which nc` 返回路径。
2. 同节同时写死：自检失败不阻塞 Agent 启动，只影响 `capabilities` 上报结果。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单要求 Agent 启动时执行能力自检并上报 capabilities JSON。
代码依据：
1. [agent/probes/udp_probe.py](agent/probes/udp_probe.py) 的 `self_test()` 只检查 Python `socket.AF_INET/SOCK_DGRAM` 是否可创建，没有检查 `nc`。
2. [agent/ws_client.py](agent/ws_client.py) 会直接把各 probe 的 `self_test()` 结果汇总为 `capabilities` 上报，因此 UDP 当前会按这套错误判定进入 `protocols` 列表。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 已把 UDP 自检标准固定为 `nc` 存在性检查，当前实现与规格直接冲突。
实现思路：
1. UDP 自检必须改为检查 Project 规定的底层依赖，而不是用 Python 语言层最小能力替代协议能力。
2. `capabilities.unsupported_reasons` 必须直接反映缺失的系统依赖，例如 `nc (netcat) not installed`。
3. 自检失败后 Agent 仍启动，但 UDP 必须稳定出现在 `unsupported`，与 Project 11.5 保持一致。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.5 为准，UDP 自检必须按 `nc` 依赖标准执行，不允许继续把“Python 能开 UDP socket”当成“UDP 协议支持”。
影响：当前 capabilities 可能把不具备 Project 规定 UDP 运行条件的节点错误标绿，进一步误导节点管理页和任务创建页。
验收标准：缺少 `nc` 的节点上报 `unsupported=["udp"]` 且给出明确原因；安装了 `nc` 后再恢复为支持。

8. Agent 一键安装链路没有按 Project 13.2 与 11.5 交付“执行后即可运行”的完整安装结果，当前脚本只装环境不交付 agent 代码。
现象：Project 把一键安装脚本和 Docker 镜像都定义成正式交付面，目标是一个安装命令即可全协议启用；但当前脚本执行完成后只会生成 venv 和启动包装脚本，最后还明确提示“你需要自己把 agent Python code 复制到安装目录”，这不是可交付的一键安装，而是半成品 bootstrap。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 13.2 明确给出 `curl -fsSL https://center-ip:9191/api/install-agent.sh | bash -s -- ...` 的一键安装方式。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 11.5 明确写死：安装脚本与 Docker 镜像应默认安装所有协议依赖，目标是在 Linux 三大发行版上实现一个安装命令全协议启用。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单把节点上线、能力发现、探测执行作为安装后的可验证结果，而不是“手动再拷一遍代码后也许可运行”。
代码依据：
1. [scripts/install-agent.sh](scripts/install-agent.sh) 在末尾明确输出 `NOTE: You need to copy the agent Python code to ${INSTALL_DIR}/`，说明脚本本身不交付 agent 代码。
2. 同文件创建的 `run.sh` 直接执行 `python3 -m agent.main`，但脚本本身并没有把 `agent/` 目录下载、复制或安装到目标机。
3. [server/api/nodes.py](server/api/nodes.py) 生成的部署命令就是调用这个脚本，因此 Web 后台当前下发的是一条无法独立完成部署的命令。
实现思路：
1. 一键安装脚本必须真正交付 agent 代码，要么从中心下载打包产物，要么直接内嵌可安装 wheel/zip 拉取逻辑。
2. 脚本执行完成后必须达到“systemd 可直接启动、Agent 可直接 auth、capabilities 可直接上报”的状态。
3. 生成部署命令的接口只能返回可独立完成安装的命令，不能再返回需要人工补文件的半成品。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 13.2、11.5、17 为准，Agent 一键安装链路必须交付完整可运行结果；不允许继续保留“脚本跑完还要手动复制 agent 代码”的中间态。
影响：当前 Web 后台给管理员的部署命令实际上不可独立完成部署，会直接破坏节点接入、能力发现和后续协议支持判断。
验收标准：新节点创建后，后台给出的安装命令在目标 Linux 机器上执行完即可直接启动 Agent、完成认证并上报完整 capabilities，无需人工补拷代码。

9. `/admin/alerts/history` 的前后端权限边界没有按 Project 9.6 锁死，当前 readonly 用户仍可进入该管理路径并读取告警历史。
现象：Project 已把“readonly 禁止访问 `/admin/*` 管理页面”写成硬规则，但当前前端路由没有给告警历史页加 admin 限制，后端历史接口也只要求登录即可。结果是 readonly 虽然进不了其他管理页，却能直接进入 `/admin/alerts/history` 并读到管理区数据。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 9.6 明确写死：readonly 访问 `/admin/*` 管理页面必须被前端路由守卫和后端 403 双重拦截。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节失败场景自测明确要求 readonly 用户访问 admin 接口返回 403。
3. 关于 [project-files/PROJECT.md](project-files/PROJECT.md) 的 9.1“readonly 可查看告警历史”与 9.6“readonly 禁止访问 `/admin/*`”之间的冲突，本轮审查已按用户明确裁定处理：以 9.6 为准。
代码依据：
1. [web/src/router/index.ts](web/src/router/index.ts) 中 `admin/alerts/history` 路由没有 `meta.requiresAdmin: true`，而其他大部分 `/admin/*` 页面都加了该限制。
2. [server/api/alerts.py](server/api/alerts.py) 的 `GET /history` 使用的是 `login_required`，不是 `admin_required`。
3. [web/src/views/LayoutView.vue](web/src/views/LayoutView.vue) 仍然把“告警历史”作为管理菜单项暴露在 `/admin/alerts/history` 路径下，说明这不是一个普通用户页，而是管理区页面。
实现思路：
1. 前端路由必须把 `admin/alerts/history` 纳入 `requiresAdmin` 保护。
2. 后端 `GET /api/alerts/history` 必须与其他 `/api/alerts/*` 管理接口一样改为 `admin_required`。
3. 管理区菜单显示逻辑也必须与角色权限一致，避免 readonly 继续看到不该进入的管理路径。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 9.6 与 17 为准，`/admin/alerts/history` 必须纳入完整的 admin 权限边界；readonly 不允许继续通过前端路由或后端接口读取这一路径的数据。
影响：如果这一点不修，当前权限模型就是不闭合的，readonly 仍可绕进一部分管理区页面，Project 写死的边界规则就被打穿了。
验收标准：readonly 用户访问 `/admin/alerts/history` 时前端被路由守卫拦回；直接请求 `GET /api/alerts/history` 时后端返回 403。

10. Center 与 Agent 之间的 WebSocket 事件命名没有按 Project 7.1、7.3、7.6 的冒号协议实现，当前整条主链路都在运行一套下划线私有事件名。
现象：Project 已把 C/S 协议事件名完全写死为 `agent:auth`、`agent:heartbeat`、`agent:probe_result`、`center:task_sync`、`agent:task_ack` 等冒号命名；但当前代码里 Agent 和 Center 实际跑的却是 `agent_auth`、`agent_probe_result`、`center_task_sync`、`agent_task_ack` 这一套下划线事件名。这个问题不是单个页面的小偏差，而是核心通信协议整体偏离了 Project。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.1 明确写死了节点上行与中心下行事件名。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.3 连接生命周期明确以这些事件名描述 auth、task_sync、probe_result、task_ack 的完整链路。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.6 继续以同一套事件名定义 config_version 同步流程。
代码依据：
1. [agent/ws_client.py](agent/ws_client.py) 实际发送的是 `agent_auth`、`agent_heartbeat`、`agent_probe_result`、`agent_probe_batch`、`agent_task_ack`。
2. [server/ws/agent_handler.py](server/ws/agent_handler.py) 实际处理函数是 `on_agent_auth()`、`on_agent_probe_result()`、`on_agent_task_ack()`，实际下发的是 `center_auth_result`、`center_task_sync`、`center_result_ack`、`center_batch_ack`。
3. [server/app.py](server/app.py) 的同步重试后台任务下发的也仍然是 `center_task_sync`，说明服务端全链路都建立在这套私有命名上。
实现思路：
1. Agent 与 Center 的 Socket.IO 事件名必须统一回收敛到 Project 写死的冒号命名。
2. 连接生命周期、任务同步、结果 ACK、批量 ACK 必须全部使用同一套规格名称，不能继续出现文档一套、代码一套。
3. Dashboard 侧的订阅协议命名修正必须与这条主链路一起处理，避免系统内同时存在两套事件风格。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.1、7.3、7.6 为准，Center-Agent 主链路事件名必须整体切换到冒号协议；不允许继续以“前后端/前后端各自能对上”作为偏离规格的理由。
影响：只要核心事件名不回到 Project，后续 AI 或人工继续补协议、写测试、做联调时都会先撞上“文档协议”和“运行协议”不一致的问题。
验收标准：Agent、Center、Dashboard 三侧的 WebSocket 事件名全部与 Project 保持一致，连接生命周期与 ACK 流程可直接按 Project 章节逐项对照。

11. 节点状态机没有按 Project 8.1 完整落地，当前只做了状态值切换，缺失“禁用后真正停任务”和“上下线通知”两条规格行为。
现象：Project 对节点状态机不仅定义了 `registered/online/offline/disabled` 四个状态，还写死了禁用节点后要断开连接、停止所有任务，以及 online/offline 切换要触发通知。但当前代码里，服务端禁用节点时确实断开了 WebSocket，可 Agent 断线后本地调度器并不会停；另外心跳检查线程只更新状态并推送 dashboard 节点状态，没有任何节点离线/恢复通知逻辑。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 8.1 明确写死：`online / offline -> disabled` 时系统行为是“断开 WebSocket 连接，停止所有该节点的任务”。
2. 同节明确写死：`online -> offline` 时要触发节点离线告警通知，`offline -> online` 时要触发节点上线恢复通知并触发断线补传流程。
代码依据：
1. [server/api/nodes.py](server/api/nodes.py) 在禁用节点时会 `socketio.disconnect()`，但没有向 Agent 发送任何“停任务”语义。
2. [agent/ws_client.py](agent/ws_client.py) 的 `on_disconnect()` 只把 `connected/authenticated` 置为 false 并停止心跳，没有调用 [agent/scheduler.py](agent/scheduler.py) 里的 `stop_all()`，因此本地探测线程会继续运行。
3. [server/app.py](server/app.py) 的 `heartbeat_checker()` 在节点 online/offline 切换时只做 `push_node_status()` 和日志记录，没有任何节点级告警/恢复通知逻辑。
4. [web/src/types/index.ts](web/src/types/index.ts) 甚至把 `Node.status` 限制成 `online | offline`，说明前端类型层也没有完整接受 `registered | disabled` 这套状态机。
实现思路：
1. 节点被禁用时，Agent 侧必须明确停掉所有调度任务，而不是只断开 socket 继续探测。
2. 节点 online/offline 状态变化必须补齐通知链路，至少要满足 Project 8.1 写死的离线通知与上线恢复通知。
3. 前端与类型层必须完整承接四态节点状态机，不允许再把 `registered/disabled` 压扁成 `offline` 的变体。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 8.1 为准，节点状态机必须完整落地到“状态值 + 系统行为 + 前端可视化”三层；不允许继续只改数据库状态字段而不落实停任务与通知语义。
影响：当前节点禁用并不能真正停止本地探测，online/offline 也没有形成完整的运维通知闭环，状态机只实现了表面的一半。
验收标准：禁用节点后 Agent 本地所有任务立即停止；节点离线和恢复上线都能触发对应通知；前端能区分 registered、online、offline、disabled 四种状态。

12. 告警状态机和告警历史表没有按 Project 8.2、6.3、12.2 完整落地，当前实现只有 `normal/alerting` 两态，恢复链路与历史字段是空壳。
现象：Project 明确写死告警状态机是 `normal -> alerting -> recovering -> normal`，恢复事件还必须写入 `alert_started_at` 和 `duration_seconds`。但当前代码里恢复时是直接从 `alerting` 回到 `normal`，没有 `recovering` 状态；同时告警历史表虽然有 `message`、`alert_started_at`、`duration_seconds` 三个字段，写库时却完全不填。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 8.2 明确写死：告警状态机包含 `recovering` 中间态。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 6.3 明确写死：`alert_history` 需要记录 `message`、`alert_started_at`、`duration_seconds`，且 `duration_seconds` 在 recovery 事件中必须填写。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的 12.2 明确写死：恢复流程要发送恢复通知并记录恢复事件到 `alert_history`。
4. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单明确要求恢复事件写入 `duration_seconds`。
代码依据：
1. [server/services/alert_service.py](server/services/alert_service.py) 的 `_alert_state` 只维护 `normal | alerting`，恢复时在 `_check_threshold()` 中直接返回 `recovery` 并把状态重置为 `normal`，没有 `recovering` 状态。
2. 同文件的 `record_alert_event()` 创建 [server/models/alert.py](server/models/alert.py) 的 `AlertHistory` 时，只写了 `task_id/event_type/metric/actual_value/threshold/notified`，没有填 `message`、`alert_started_at`、`duration_seconds`。
3. [web/src/types/index.ts](web/src/types/index.ts) 的 `AlertHistory` 类型也只声明了精简字段，没有把 `message`、`alert_started_at`、`duration_seconds` 接出来，前端层同样没有承接完整规格。
实现思路：
1. 告警状态机必须显式补齐 `recovering` 语义，不允许继续用“直接回 normal”替代规格状态。
2. 告警触发时必须记录 alert 起点；恢复时必须按该起点回填 `alert_started_at` 与 `duration_seconds`。
3. 告警历史 API、前端类型和管理页表格都必须承接完整字段，而不是只展示最小子集。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 8.2、6.3、12.2、17 为准，告警状态机与告警历史表必须按完整规格实现；当前“两态状态机 + 空字段表结构”不能视为已完成。
影响：如果恢复链路不补齐，当前告警历史无法回答“这次告警从何时开始、持续了多久、是否经历恢复”，Project 定义的运维可追溯性就不存在。
验收标准：系统内部存在 `recovering` 语义；恢复事件入库时带有 `alert_started_at` 与 `duration_seconds`；前端和 API 都能读取并展示这些字段。

13. `result_id` 幂等去重没有按 Project 7.4.1 落地成持久检查，当前只是一个 10 分钟内存去重缓存，无法覆盖重启后和长时补传场景。
现象：Project 写的是“中心写入 InfluxDB 前检查 `result_id` 是否已存在”，目标是无论因为网络抖动、重连补传还是重复发送，都不能重复入库。但当前实现的 `check_result_exists()` 只是检查一个 `_DEDUP_TTL = 600` 秒的内存 `OrderedDict`；服务重启后缓存丢失，超过 10 分钟的重复补传也会穿透去重。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.4.1 明确写死：中心写入 InfluxDB 前检查 `result_id` 是否已存在，已存在则跳过写入但仍返回 ACK。
2. 同节明确写死：目标效果是即使同一条数据发送两次，也不会在数据库中出现重复记录。
代码依据：
1. [server/services/influx_service.py](server/services/influx_service.py) 的 `check_result_exists()` 明确写着 `using in-memory dedup cache`，并把 `_DEDUP_TTL` 固定为 600 秒。
2. 同文件虽然把 `result_id` 写入了 Influx field，但没有任何基于 Influx 查询或持久索引的“已存在检查”。
3. [server/ws/agent_handler.py](server/ws/agent_handler.py) 的实时结果和批量补传都只依赖这个内存缓存做去重。
实现思路：
1. `result_id` 去重必须升级为跨进程、跨重启、跨补传窗口的持久幂等检查，不能再只依赖短 TTL 内存缓存。
2. 可以用独立幂等表、持久索引或 Influx 可查询去重标记实现，但必须满足 Project 的“入库前已存在检查”语义。
3. 内存缓存最多只能作为性能优化层，不能作为唯一正确性来源。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 7.4.1 为准，`result_id` 幂等必须以持久去重为准；当前 10 分钟内存缓存只能算优化，不能算规格完成。
影响：一旦中心重启或补传窗口拉长，当前系统就可能把同一条历史结果再次写入时序库，直接破坏补传协议的幂等性承诺。
验收标准：无论中心是否重启、重复数据是否跨越 10 分钟窗口，同一个 `result_id` 都只会被实际入库一次。

14. Agent 本地缓存的补传生命周期没有按 Project 6.4 完整落地，`batch_id` 与 `retry_count` 目前只是表结构占位，实际发送流程没有使用。
现象：Project 不只是要求 `local_results` 表里有这些列，而是要求补传时能记录所属批次、维护发送/重试状态，形成可解释的本地缓存生命周期。但当前代码里，实时发送只会把记录从 `pending` 改成 `sent`，批量补传时既不会写入 `batch_id`，也不会累计 `retry_count`，导致表结构和真实行为脱节。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 6.4 明确写死：`local_results` 需要包含 `batch_id` 与 `retry_count`，并且断线重连后要把未 ACK 记录组装为 batch 发送。
2. 同节生命周期写死：补传流程需要能区分待发送、已发送待 ACK、已确认，并以批次为单位处理 `center:batch_ack`。
代码依据：
1. [agent/local_cache.py](agent/local_cache.py) 虽然建了 `batch_id`、`retry_count` 两列，但只有 `store_result()`、`mark_sent()`、`mark_acked()`、`mark_batch_acked()`，没有任何设置 batch_id 或递增 retry_count 的方法。
2. [agent/ws_client.py](agent/ws_client.py) 的 `_backfill()` 只是从 `get_unacked_results()` 取 payload 后直接 emit `agent_probe_batch`，没有把本地记录写上对应的 `batch_id`。
3. 同文件补传发送时也没有任何 retry_count 递增逻辑，说明当前本地缓存无法反映某条数据被补传了几次。
实现思路：
1. 本地缓存层必须补齐“批量发送前写入 batch_id”和“每次补传尝试递增 retry_count”的接口。
2. 批量 ACK 时不仅要按 accepted_ids 改 `acked`，还要保留可审计的 batch 关联关系。
3. `local_results` 的字段不能只停留在建表，必须真实承载补传生命周期。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 6.4 为准，Agent 本地缓存必须完整实现 batch 补传生命周期；`batch_id` 和 `retry_count` 不允许继续只作为未使用的占位字段存在。
影响：当前补传虽然“能发”，但本地缓存已经失去 Project 设计的可追踪性，后续排查某条结果到底属于哪次补传、重试了几次会直接失去依据。
验收标准：每条参与补传的本地记录都能看到所属 `batch_id` 和累计 `retry_count`；批量 ACK 后状态与批次关系仍然可追踪。

15. 任务详情页没有按 Project 10.3 使用 ECharts `markArea` 标记异常区间，告警时段在图表上不可见。
现象：Project 明确要求把告警触发区间用半透明红色区域直接打在图表底图上，帮助运维人员一眼看到异常时间段；但当前详情页图表虽然有 tooltip、dataZoom 和多序列绘制，却完全没有把告警历史转换成 `markArea` 的逻辑，告警区间只能靠人工猜时间点。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.3 明确写死：图表支持异常区间标记（ECharts `markArea`），并在悬停时显示告警规则和持续时间。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单明确要求图表上能用 `markArea` 标注告警时段。
代码依据：
1. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 的 `updateChart()` 只构造了延迟、丢包、抖动三类 `series`，没有任何 `markArea` 配置。
2. 当前详情页也没有加载或关联告警历史数据，自然无法把告警区间渲染到图表上。
3. 现有 tooltip 只展示当前采样点数值，没有任何“异常区间规则/持续时间”的联动信息。
实现思路：
1. 详情页必须接入告警历史或异常区间数据源。
2. 将每段 `alert -> recovery` 区间转换为 ECharts `markArea`，并附带规则类型与持续时长说明。
3. 该标记应与当前时间范围联动，避免长周期和短周期下显示错位。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.3 与 17 为准，任务详情页必须补齐异常区间 `markArea`；不允许继续只画数值曲线、不画异常时段。
影响：当前图表只能显示“数值怎么变”，不能显示“哪段时间系统已经判定进入告警”，前端可视化明显低于 Project 写死的可观测性要求。
验收标准：详情页图表上可直接看到半透明红色异常区间；悬停可读出对应规则与持续时间。

16. 任务详情页没有按 Project 10.4 做协议专属图表分化，HTTP、DNS、TCP 仍被压扁在通用 Ping 图里。
现象：Project 对不同协议的图表组合写得非常具体，HTTP 要有阶段堆叠面积图和状态码散点图，DNS 要有解析 IP 变更记录，TCP 要显示连接成功率，ICMP 要有抖动折线图。但当前详情页只有一套通用图表配置，不根据 `protocol` 分支渲染协议专属视图，导致探测结果里已有的 `dns_time`、`tcp_time`、`tls_time`、`ttfb`、`status_code`、`resolved_ip` 等字段在详情页基本被浪费。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.4 明确写死了五类协议各自应展示的图表组合。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.3 同时强调：不同协议展示不同指标组合。
代码依据：
1. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 内部没有读取当前任务 `protocol` 并分支渲染不同图表布局的逻辑。
2. 同文件 `updateChart()` 固定只围绕 `latency`、`packet_loss`、`jitter` 组织通用 `series`，没有使用 `status_code`、`dns_time`、`tcp_time`、`tls_time`、`ttfb`、`resolved_ip`。
3. 搜索全前端代码，协议专属的 HTTP 阶段图、状态码散点图、DNS 解析 IP 变更记录组件均不存在。
实现思路：
1. 详情页必须按任务协议切换图表布局，而不是一套配置硬套全部协议。
2. HTTP/HTTPS 需要拆出总响应时间、阶段耗时堆叠面积图、状态码散点图。
3. DNS 需要展示解析时间、解析成功率与解析 IP 变更记录；TCP/UDP 也要回到各自的协议语义。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.4 为准，任务详情页必须实现协议专属图表组合；当前“全部协议共用一张 Ping 图”的方案不合格。
影响：现在虽然底层已经能采集 HTTP/DNS 的多维指标，但前端详情页没有把这些指标转化成可读的协议视图，导致 Project 的高保真可视化要求落空。
验收标准：不同协议进入详情页后能看到与 Project 一致的专属图表组合，HTTP/DNS 等协议字段被真实可视化而不是闲置。

17. 系统设置里的页面标题/副标题自定义没有按 Project 10.6 落地到前端全局 UI，当前既缺少完整设置入口，也没有全局生效链路。
现象：Project 明确要求系统设置支持页面标题/副标题自定义，但当前管理页只暴露了心跳窗口、离线阈值、默认超时等技术参数，没有 `site_title` / `site_subtitle` 的表单项；同时主布局仍然硬编码显示 `NSR v{{ appVersion }}`，也没有任何 `document.title` 或全局站点标题更新逻辑。也就是说，这项功能不只是“保存后不生效”，而是“前后台都没闭环”。
Project 依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 明确把“系统设置 | 页面标题/副标题自定义”列为后台功能。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 17 节自测清单也明确包含“系统设置（页面标题/副标题）”。
代码依据：
1. [server/api/settings.py](server/api/settings.py) 的默认设置里虽然已有 `site_title` 与 `site_subtitle`。
2. 但 [web/src/views/admin/SettingsView.vue](web/src/views/admin/SettingsView.vue) 没有任何 `site_title` 或 `site_subtitle` 输入项。
3. [web/src/views/LayoutView.vue](web/src/views/LayoutView.vue) 顶部品牌区仍硬编码为 `NSR` 和版本号，没有读取系统设置。
4. 全前端也不存在 `document.title` 更新或全局设置加载逻辑。
实现思路：
1. 管理后台必须补齐页面标题/副标题输入项。
2. 前端布局层必须在启动或登录后拉取系统设置，并把 `site_title` / `site_subtitle` 应用到导航头、品牌区和页面标题。
3. 设置保存后需要有明确的全局刷新机制，避免“后台保存成功但前台仍是旧文案”。
决定方向：以 [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.6 与 17 为准，系统设置的页面标题/副标题自定义必须形成“可配置 + 可读取 + 可生效”的完整链路；当前半成品状态不能视为已实现。
影响：管理员当前无法真正定制站点品牌展示，Project 里写死的系统设置能力没有交付到最终 UI。
验收标准：管理员可在系统设置里修改标题和副标题，保存后导航头、品牌区及页面标题能一致更新。

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

### v0.124 已完成

本版本已完成的事项：

1. 已完成任务详情页范围与 bucket 语义的代码复查，确认前端已补齐 `3d / 14d` 选项并开始按 Project 的粒度区分原始样本与聚合桶。
2. 已完成详情页缩放态、数据点数展示、安全尾巴和窗口抖动方向的第一轮实现核对，确认相关逻辑已经进入当前代码，不再停留在空白建议阶段。
3. 已完成任务编辑页字段收敛的代码复查，确认编辑模式下源节点、协议、目标类型、目标地址等未被后端支持的字段已经被前端禁用，不再继续作为现状问题保留。

验收结果：已完成，后续不再把这些已核实的实现项重复列为当前问题。

### v0.125 已完成

本版本已完成的事项：

1. 已确认 `icmp jitter` 的实现方向：按前端最近 10 个 `latency` 点计算窗口抖动，文档方向已写死。
	该项经本轮审查后按用户明确选择保留，不作为与 [project-files/PROJECT.md](project-files/PROJECT.md) 的冲突项回退。
2. 已确认任务编辑接口的事务语义已从“500 伪装保存失败”收敛为“保存成功但可返回 `sync_status=pending`”的方向，并完成代码复查。
3. 已完成对 `agent/network_tools/` 目录的第一轮审查，确认仓库当前已经有本地 `network_tools` 目录，但其实现来源是否符合 Project 仍需继续向 v0.126 的全仓规格审查推进。

验收结果：已完成，后续以 v0.126 的全仓规格审查结果作为新的当前问题基线。

---



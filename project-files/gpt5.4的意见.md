# 给 AI Agent 的执行 Prompt（v5 终稿）

你现在要在以下真实项目中完成一次性修复，不要把已完成的问题重新打开，不要自行扩展需求，不要偏离本文列出的范围。

## 你的目标

把项目中**当前仍未解决**、且已经被代码复核确认的剩余问题一次性改好，使工程与以下两份权威文档对齐：

1. 工程文档：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\project-files\PROJECT.md`
2. 权威 bug 报告：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\project-files\gpt5.4-bug-rep.md`

## 你必须工作的真实路径

1. 主项目根目录：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG`
2. 外部探测核心真实对照目录：`D:\wingsrabbit-ovo\Network-Monitoring-Tools`

以上两个路径都已核实存在。外部探测核心目录下当前可见的真实子目录包括：

1. `curl_ping`
2. `dns_lookup`
3. `icmp_ping`
4. `tcp_ping`
5. `udp_ping`

## 这次只允许你解决的剩余问题

### 任务 1：把探测核心真正对齐到 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`

当前 `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools` 虽然目录结构完整，但仍然是本仓库自写实现，不是 Project / bug-rep 要求的真实底层来源。

你必须完成的结果：

1. `agent/network_tools/icmp_ping`
2. `agent/network_tools/tcp_ping`
3. `agent/network_tools/udp_ping`
4. `agent/network_tools/curl_ping`
5. `agent/network_tools/dns_lookup`

以上五类协议的真实测量核心，必须与 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 保持真实一致的来源关系，而不是继续保留“参考上游的仓内自写实现”。

你可以选择的实现方式只有两类：

1. 直接把外部仓库中的真实实现同步进当前项目的 `agent/network_tools/`。
2. 或者建立明确、稳定、可运行的导入/打包机制，让当前项目实际执行时调用的就是 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的真实实现。

但无论你选哪种方式，验收标准都一样：

1. 当前项目运行时真正使用的底层探测核心必须来自 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`。
2. 不允许继续保留“目录名字一样，但代码其实还是本仓库自己写的”这种伪对齐状态。

### 任务 2：保持 `probes/*.py` 只做适配层，不再承担底层探测实现

需要重点核对并修正的文件包括：

1. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\icmp_probe.py`
2. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\tcp_probe.py`
3. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\udp_probe.py`
4. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\http_probe.py`
5. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\dns_probe.py`

你必须保证这些文件最终只做下面这些事：

1. 参数适配
2. 返回值归一化
3. 能力发现接口
4. 上层协议名注册

你不应继续把真实测量逻辑散落在这些适配层中。

### 任务 3：修正 TCP 能力发现自检逻辑

当前文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\tcp_probe.py`

当前问题已经核实存在：

1. 现在的 `self_test()` 仅检查 `hasattr(socket, 'create_connection')`。
2. 这与 `PROJECT.md` 11.5 中写死的“`socket.create_connection()` 可正常调用”不一致。

你必须把它修到以下标准：

1. 不再只是检查属性存在。
2. 自检逻辑要体现“该能力可被真实调用”的语义。
3. 仍然保留 `PROJECT.md` v1.5 的硬规则：**即使 TCP 自检失败，也绝不能阻塞 Agent 启动。**

如果你对“可正常调用”的具体实现方式有多种可选方案，你必须选择：

1. 最保守
2. 最不依赖不稳定外部环境
3. 最不容易误伤正常启动

的那一种。

## 这次明确不要动的内容

以下问题这次已经确认修复完成，不要重复返工，不要把它们重新改坏：

1. 任务同步状态机进入 `pending`
2. UDP 自检按 `nc` 判定
3. Agent 一键安装下载 `agent-package.tar.gz`
4. InfluxDB 持久化去重
5. 告警状态机 `recovering` 与恢复字段写入
6. Dashboard 冒号事件名与 `connect_error.data.code` 读取
7. `/admin/alerts/history` 的 admin 权限边界
8. 节点能力展示与任务创建兼容性 warning
9. 详情页 `markArea` 与协议专属图表
10. 系统标题/副标题配置生效链路

除非你在实现剩余问题时被这些模块真实阻塞，否则不要重新打开它们。

## 你开工前必须先做的核查

在正式改代码前，你必须先逐项核查并确认：

1. `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 下五类协议实现的真实入口文件与当前项目预期接口如何映射。
2. 当前 `agent/network_tools/*` 与外部仓库同名目录之间，哪些是完全不同实现，哪些只是包装差异。
3. 当前 `probes/*.py` 的返回数据结构与上层 `ProbeResult` 对接要求是否一致。
4. TCP 自检修正后，是否仍满足“失败不阻塞启动”的硬规则。

## 你完成后必须满足的验收结果

1. 当前项目实际使用的五类探测核心，真实来源对齐到 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`。
2. `agent/probes/*.py` 保持为适配层，不再继续承担底层探测实现。
3. `agent/probes/tcp_probe.py` 的 `self_test()` 不再只是 `hasattr()`。
4. Agent 启动链路仍然满足“单协议自检失败不阻塞整体启动”。
5. 不把本文件第三部分已经确认修掉的问题重新改坏。

## 你的输出要求

你完成代码修改后，必须能清楚回答：

1. 你改了哪些文件。
2. 每个文件为什么要改。
3. 哪些改动是为了对齐 `PROJECT.md`。
4. 哪些改动是为了对齐 `gpt5.4-bug-rep.md`。
5. 你如何证明底层探测核心现在真的来自 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`，而不是继续停留在“看起来像”的状态。

---

## 这份文档的五轮自校对结果

### 第 1 轮：问题范围收缩

我先把范围收缩到“当前仍未解决的问题”，把已经修掉的旧问题从当前问题列表中剔除，避免给 AI Agent 错的目标集。

### 第 2 轮：路径与对象核实

我核实了以下真实路径存在：

1. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG`
2. `D:\wingsrabbit-ovo\Network-Monitoring-Tools`
3. 外部探测核心下的五类协议目录都存在。

### 第 3 轮：当前已修复项复核

我复核并确认了一批 Gemini 中已经过时的问题，确保它们不再被误写为“当前未解决”，包括：UDP 自检、任务同步 pending、持久化去重、告警恢复字段、Dashboard 冒号事件、安装脚本、前端图表和设置页等。

### 第 4 轮：AI Agent 可执行性增强

我把原先偏评审风格的内容，补成了 AI Agent 可直接执行的 prompt，包括：

1. 真实路径
2. 明确任务边界
3. 必做项
4. 不要动的项
5. 开工前核查项
6. 完工验收项

### 第 5 轮：歧义清理

我最后清理了容易让 AI Agent 自由发挥的表述，重点把下面几件事写死：

1. 这次只修剩余问题，不回头重做已完成项。
2. “探测核心来源对齐”不是口头对齐，而是实际运行时来源对齐。
3. TCP 自检修复的同时，不能破坏“失败不阻塞启动”的硬规则。

本轮自校对后，当前文档目标已经从“评审意见”升级为“可直接交给 AI Agent 执行的修复说明”。

---

# GPT5.4 的意见

任务名称：复核 NetworkStatus-Rabbit-NG 当前工程与文档一致性

最后整理时间：2026-03-24

当前审查基线：

1. 项目根目录：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG`
2. 权威工程文档：`project-files/PROJECT.md`
3. 权威 bug 报告：`project-files/gpt5.4-bug-rep.md`
4. 本次口径：只保留**当前仍未解决**、且已被代码复核确认的问题；已经落地的问题不再混入“当前问题”里。

---

## 零、结合 Gemini 3.1 Pro 意见后的取舍说明

这一节是专门写给后续继续维护这份文档的人看的，目的只有一个：

**说明我从 Gemini 的意见里知道了什么可以加入，知道了什么不可以加入，以及为什么不能直接加入。**

### 1. 我从 Gemini 那里知道了什么，这些内容可以加入

Gemini 这份意见里，**真正可以吸收进当前文档的，不是新增出很多全新问题，而是对现有核心问题的“强调点”和“表述角度”**。可吸收的点主要有三类：

1. 它再次确认了 `agent/network_tools/` 当前具有明显的“同名目录已对齐、真实来源未对齐”的伪完成特征。
2. 它提醒需要把“HTTP/DNS 虽然已经结构收敛到 `network_tools + probes`，但底层仍不是文档要求的真实来源”单独讲清楚，避免后续维护者误以为这一层已经完全收口。
3. 它强化了一个写法上的重点：当前剩余问题已经不是“大量业务页面没做”，而是**底层探测基线与最终实现来源**还没有彻底闭环。

基于这三点，我对本文做的升级不是“机械把 Gemini 的问题继续加 10 条”，而是：

1. 保留当前真正成立的问题主线。
2. 让“探测核心来源不对齐”与“协议层虽然结构收敛但真实来源仍不对齐”这两个层次写得更明确。
3. 明确告诉后续读者：这已经不是 UI 零碎缺项问题，而是底座基线问题。

### 2. 我从 Gemini 那里知道了什么，但我认为这些内容不可以直接加入“当前未解决问题”

Gemini 文档里有不少条目，在更早版本里可能是成立的，但**按当前仓库代码复核，它们已经不再是“当前未解决问题”**，因此不能直接并入本文第二部分。原因不是我想省略问题，而是：

**如果把已经修掉的旧问题继续写进“当前问题”，这份文档本身就会再次失真。**

当前我明确认为**不能直接加入**的，主要包括这些类型：

1. 任务同步状态机未推进：当前 `server/api/tasks.py` 已在任务创建、更新、删除、启停后调用 `mark_sync_pending()`，旧结论不能继续保留为“当前未解”。
2. UDP 自检仍是 Python socket 降配判断：当前 `agent/probes/udp_probe.py` 已改为按 `nc` 是否存在判定，Gemini 这里已经过时。
3. Agent 一键安装仍是半成品：当前 `scripts/install-agent.sh` 已改为下载 `/api/agent-package.tar.gz` 并解压，旧结论不能再直接成立。
4. InfluxDB 去重仍只是 600 秒内存缓存：当前 `server/services/influx_service.py` 已补了持久化 SQLite 去重层，这条不能再按旧说法并入。
5. 告警状态机缺失 `recovering` 和 `duration_seconds`：当前 `server/services/alert_service.py` 已经补齐 `recovering` 语义与恢复事件字段写入。
6. Dashboard 订阅事件仍是下划线私有命名、前端未处理 `WS_AUTH_FAILED`：当前前后端都已经使用冒号事件名，前端也已按 `err.data.code` 处理 `connect_error`。
7. `/admin/alerts/history` 权限边界未收紧：当前前端路由与后端接口都已收紧为 admin。
8. 任务创建缺少协议兼容性提示、节点列表缺少 capabilities 展示：当前 `TasksView.vue` 与 `NodesView.vue` 都已经补齐。
9. 详情页缺少 `markArea`、缺少协议专属图表、系统标题副标题未生效：当前 `TaskDetailView.vue`、`SettingsView.vue`、`LayoutView.vue` 已经补上相应链路。

这些点之所以**不可以加入**当前未解决问题，原因都相同：

1. 它们在历史上可能确实存在。
2. 但现在代码已经不是那个状态了。
3. 如果继续写进“当前问题”，会误导后续开发和评审，把精力再次浪费在已经完成的项上。

### 3. 这次升级后的处理原则

因此，这次结合 Gemini 的结果，我采取的原则是：

1. **吸收它仍然成立的洞察，不照单全收它的旧问题列表。**
2. **可以增强论证的内容加入；已经被当前代码推翻的内容不加入。**
3. **宁可少写，也不把过期问题重新写回“当前未解决问题”。**

---

## 一、先说结论

这次我重新按“工程是否已经真正落地到文档和 bug-rep 的最终要求”去看当前仓库。

结论比上一次短很多：

1. **项目与 PROJECT.md 是部分对齐。**
2. **项目与 gpt5.4-bug-rep 也是部分对齐。**
3. 当前真正还没解决的问题，已经不算多，但有两类问题仍然是硬伤：
   - **探测核心的真实来源仍未对齐 Project/bug-rep 写死的“直接集成 Network-Monitoring-Tools”要求。**
   - **TCP 能力发现的自检逻辑仍未按 v1.5 最终规范真正落地。**

也就是说，现在不是“系统大面积没做完”，而是：

1. 大量此前 bug-rep 里的前后端闭环问题其实已经修掉了。
2. 但最底层、最原则性的那层“探测核心来源”仍然没有彻底归位。
3. 再加上一个 v1.5 明确点名修正的 TCP 自检细节还没收尾，所以还不能说完全对齐。

---

## 二、当前仍未解决的问题

### 1. 整个探测核心仍未按 Project 11.4 真正接入本地 Network-Monitoring-Tools，当前仍是仓内自写实现

#### 现象

仓库表面上已经有 `agent/network_tools/` 目录，也已经把 HTTP、DNS、ICMP、TCP、UDP 都整理成了 `network_tools + probes adapter` 的两层结构；但继续往下核对后可以确认，**当前这里仍然不是对本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的真实直接集成，而是本仓库自己写的一套实现，再用“参考上游”的方式去贴近它。**

这意味着当前项目在“目录结构”和“命名方式”上已经对齐了 Project，但在 **“实现来源”** 这一层仍然没有对齐。

#### Project / bug-rep 依据

1. `project-files/PROJECT.md` 的 1.3 明确写死：`Network-Monitoring-Tools` 是底层探测模块，作为探测核心直接集成。
2. `project-files/PROJECT.md` 的 11.4 明确写死：`probes/*.py` 只是适配层，真正的探测核心应落在 `agent/network_tools/`。
3. `project-files/gpt5.4-bug-rep.md` 的第 1 条进一步把要求收紧为：`agent/network_tools/` 必须承载来自本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的真实探测核心，而不是仓内自写替代物。

#### 代码依据

1. `agent/network_tools/icmp_ping/__init__.py` 仍然是本仓库自写的 `subprocess + ping` 解析逻辑，文件头虽然写了“参考上游”，但它本身就是本仓库代码，不是外部仓库原始实现。
2. `agent/network_tools/tcp_ping/__init__.py` 仍然是本仓库自写实现，不是直接来自本地 `Network-Monitoring-Tools` 的原始代码。
3. `agent/network_tools/udp_ping/__init__.py` 仍然是本仓库自写实现，不是直接来自本地 `Network-Monitoring-Tools` 的原始代码。
4. `agent/network_tools/curl_ping/__init__.py` 仍然是本仓库自写的 `curl`/`requests` 包装逻辑，同样只是“参考上游”，不是直接引入上游探测核心。
5. `agent/network_tools/dns_lookup/__init__.py` 仍然是本仓库自写的 `dig/nslookup` 包装逻辑，也不是直接来自本地 `Network-Monitoring-Tools` 的原始实现。
6. `requirements-agent.txt` 中没有任何能证明当前仓库以某种方式安装、引用或打包本地 `Network-Monitoring-Tools` 的依赖或接入痕迹。

#### 为什么这条仍然算硬伤

这不是代码风格问题，也不是“实现得像不像”的问题，而是**规格落地来源不一致**的问题。

文档和 bug-rep 要的是：

1. 探测核心能力来源被锁死。
2. 后续协议正确性以那个既定工具仓库为基线。
3. 当前项目只做适配和归一化，而不是继续在本仓库里维护一套“相似实现”。

如果这一层不回到真实上游实现，那么后面所有协议行为、边界条件、统计语义，都会继续处于“名字看起来对了，但底层其实仍然是另一套实现”的状态。

#### 决定方向

以 `PROJECT.md` 和 `gpt5.4-bug-rep.md` 为准：

1. `agent/network_tools/` 必须替换或重构为真实承载本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的原始探测核心。
2. `agent/probes/*.py` 只保留参数适配、返回值归一化和能力发现接口。
3. 不允许继续把“目录名一致”当作“实现来源一致”的替代。

#### 验收标准

1. `agent/network_tools/` 中的核心实现来源与文档要求一致。
2. 五类协议的真实测量入口都统一收敛到该目录。
3. `probes/*.py` 不再承担底层探测实现，只承担适配职责。

---

### 2. 所有 C/S 探测组件虽然结构上已收敛到 `network_tools + probes`，但底层仍未回到 bug-rep 要求的唯一真实来源

#### 现象

相较于更早的状态，HTTP 与 DNS 现在已经不再直接在 `probes/*.py` 中裸跑系统命令，而是改成调用 `agent.network_tools.curl_ping` 与 `agent.network_tools.dns_lookup`。这说明结构层面确实比之前收敛了。

但问题是：**它们收敛到的仍然是本仓库自写的 `network_tools`，而不是 bug-rep 要求的那份本地 `Network-Monitoring-Tools` 真实实现。**

所以这一条当前属于“结构部分修正了，但根因还没修到位”。

#### Project / bug-rep 依据

1. `project-files/PROJECT.md` 的 11.4 把探测架构写死为：`network_tools` 负责原始测量，`probes` 负责适配。
2. `project-files/gpt5.4-bug-rep.md` 的第 2 条进一步写死：所有 C/S 测试组件都必须统一落在本地 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 体系下，不能只是“看起来像同一层结构”。

#### 代码依据

1. `agent/probes/http_probe.py` 现在确实走了 `agent.network_tools.curl_ping.probe`，但它依赖的 `agent/network_tools/curl_ping/__init__.py` 仍是仓内自写实现。
2. `agent/probes/dns_probe.py` 现在确实走了 `agent.network_tools.dns_lookup.probe`，但对应 `agent/network_tools/dns_lookup/__init__.py` 也仍是仓内自写实现。
3. `agent/probes/tcp_probe.py`、`agent/probes/icmp_probe.py`、`agent/probes/udp_probe.py` 也是同样问题：当前只是包装本仓库自己的 `agent.network_tools.*`。

#### 为什么这条需要单列

第 1 条说的是“探测核心来源总原则没有对齐”；这条说的是“**五类协议的实际统一来源仍然没有真正归到同一真实基线**”。

也就是说，这不是重复，而是第 1 条在协议维度上的展开：

1. 根因是探测核心来源没锁死。
2. 直接表现是五类协议虽然结构统一了，但底层仍不是文档要求的那一套真实来源。

#### 决定方向

以 `gpt5.4-bug-rep.md` 为准：

1. 五类协议的真实测量逻辑必须统一归到真实 `Network-Monitoring-Tools`。
2. `probes/` 层不应再持有任何“另一套底层实现”。
3. 之后才能说“所有 C/S 组件统一在同一真实探测体系里”。

#### 验收标准

1. HTTP、DNS、ICMP、TCP、UDP 五类协议底层都来自同一份真实探测核心。
2. `probes/*.py` 中只剩适配与归一化，不再隐含第二套实现来源。

---

### 3. TCP 能力发现的自检逻辑仍未按 Project v1.5 和 GPT5.4 第五轮意见真正落地

#### 现象

`PROJECT.md` v1.5 已经把这一点改得很明确：

1. TCP 自检不再允许写成“连接自身 WS 端口”。
2. 应改为“检查 Python `socket` 模块可导入且 `socket.create_connection()` 可正常调用”。

但当前代码里，TCP 自检仍然只做了：

1. `import socket as s`
2. `assert hasattr(s, 'create_connection')`

也就是：**它只检查这个 API 名字在不在，并没有真正验证这条能力是否能被正常调用。**

#### Project / GPT5.4 依据

1. `project-files/PROJECT.md` 的 11.5 已明确写死：TCP 自检方式是“`socket` 模块可导入且 `socket.create_connection()` 可正常调用”。
2. `project-files/GPT5.4的建议-5.md` 里把这一点列为本轮第一优先级，原因是旧版“连自身 WS 端口”的逻辑不成立。

#### 代码依据

1. `agent/probes/tcp_probe.py` 中当前 `self_test()` 的实现为：导入 `socket` 模块并断言存在 `create_connection` 属性，然后直接返回成功。
2. 这与 `PROJECT.md` 当前写死的“可正常调用”存在直接落差。

#### 为什么这条仍然成立

这里的关键不是“要不要真的联网去测某个目标”，而是：**当前实现明显还停留在“属性存在性检查”，没有达到文档最终要求的那一层能力判定。**

这意味着：

1. 代码没有严格落地 v1.5 的修订意图。
2. 如果继续按“当前已对齐”处理，就等于又把一个本来已经在文档里收死的实现细节放回了模糊状态。

#### 决定方向

以 `PROJECT.md` v1.5 为准：

1. TCP 自检至少要落到“真实调用该能力”的层级，而不是只检查属性存在。
2. 同时保留 v1.5 写死的另一条硬规则：**自检失败不阻塞 Agent 启动**。

#### 验收标准

1. `TCPProbe.self_test()` 不再只是 `hasattr()` 级别检查。
2. 能力发现的 TCP 支持判定与 `PROJECT.md` 11.5 的最终语义一致。

---

## 三、这次特别说明：哪些旧问题我确认已经修掉了

为了避免后续继续拿旧版 bug 清单当“当前状态”，这里把这次复核中确认已经落地的项单独列出来。

下面这些问题，**本次代码复核时已经不应再算作当前未解决问题**：

1. 任务同步状态机在任务增删改时进入 `pending`：`server/api/tasks.py` 现在已经在创建、更新、删除、启停后调用 `task_service.mark_sync_pending()`。
2. 节点管理页协议支持状态展示：`web/src/views/admin/NodesView.vue` 现在已经有“协议支持”列，并读取 `capabilities` 渲染支持/不支持状态。
3. 任务创建时协议兼容性 warning：`web/src/views/admin/TasksView.vue` 现在已经根据节点 `capabilities` 和所选协议显示 warning。
4. Dashboard 订阅事件命名：当前前后端都已经使用 `dashboard:subscribe_task` / `dashboard:unsubscribe_task` 这套冒号事件名。
5. 前端 `connect_error` 读取方式：`web/src/composables/useSocket.ts` 现在已经按 `err?.data?.code` 读取，并在 `WS_AUTH_FAILED` 时跳转登录页。
6. UDP 自检标准：`agent/probes/udp_probe.py` 现在已经改为按 `nc` 是否存在来判定。
7. Agent 本地缓存 `batch_id` / `retry_count`：`agent/local_cache.py` 和 `agent/ws_client.py` 现在已经在补传路径里真实使用这两个字段。
8. `result_id` 幂等去重：`server/services/influx_service.py` 现在已经有持久化 SQLite 去重层，不再只是 10 分钟内存缓存。
9. 告警状态机与恢复字段：`server/services/alert_service.py` 现在已经有 `recovering` 语义，并在恢复事件中写入 `message`、`alert_started_at`、`duration_seconds`。
10. `/admin/alerts/history` 权限边界：前端路由和后端接口现在都已经收紧到 `admin`。
11. 任务详情页异常区间标记与协议专属图表：`web/src/views/TaskDetailView.vue` 现在已经有 `markArea` 和协议分支图表逻辑。
12. 系统设置中的页面标题/副标题：`web/src/views/admin/SettingsView.vue` 与 `web/src/views/LayoutView.vue` 现在已经形成配置和前端生效链路。
13. Agent 一键安装链路：`scripts/install-agent.sh` 现在已经改为下载 `/api/agent-package.tar.gz`，不再是“脚本执行后还要手动复制 agent 代码”的半成品。

换句话说，这次不要再把上面这些旧问题和“当前未解决问题”混在一起。真正仍需处理的，集中在本文件第二部分那几条。

---

## 四、最终判断

如果继续用“是否已经可以低自由度地交给 AI Agent 实现/维护”这个标准来打分，我这次的判断是：

1. **整体已经接近收尾，但还不能算完全对齐。**
2. **当前剩余问题数量不多，但都落在底层基线和实现来源这一层，所以不能用‘只是小问题’轻轻带过。**

现在距离完全对齐，核心只剩两步：

1. 把探测核心的真实来源彻底锁回 `Network-Monitoring-Tools`。
2. 把 TCP 自检从“属性存在”补到文档要求的“能力真实可调用”。

这两步完成后，当前仓库与 `PROJECT.md`、`gpt5.4-bug-rep.md` 的一致性才可以从“部分对齐”提升到“基本/完全对齐”。
# 给 AI Agent 的最终执行规范（v3 定稿）

本文件已经过 3 轮消歧，目标只有一个：

**把它直接交给 AI Agent 后，AI Agent 可以一次性完成当前项目剩余修复，不再靠自己补设计，不再误改已完成模块，不再自写新的底层探测实现。**

---

## 0. 真实路径与真实对象

你必须基于以下真实路径工作，不允许虚构路径，不允许把“参考上游”当成“已接入上游”。

### 主项目

`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG`

### 外部探测核心项目

`D:\wingsrabbit-ovo\Network-Monitoring-Tools`

### 已核实存在的外部探测核心目录

1. `D:\wingsrabbit-ovo\Network-Monitoring-Tools\icmp_ping`
2. `D:\wingsrabbit-ovo\Network-Monitoring-Tools\tcp_ping`
3. `D:\wingsrabbit-ovo\Network-Monitoring-Tools\udp_ping`
4. `D:\wingsrabbit-ovo\Network-Monitoring-Tools\curl_ping`
5. `D:\wingsrabbit-ovo\Network-Monitoring-Tools\dns_lookup`

### 当前项目中必须被修正的相关目录

1. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools`
2. `D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes`

---

## 1. 这次唯一允许采用的总体策略

### 策略：把外部探测核心完整打包进 agent，禁止 AI 再自写底层探测实现

你必须采用下面这条策略，不允许自由发挥成别的做法：

1. 把 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` **完整打包**进入当前项目的 `agent` 目录下。
2. 打包后的这份代码，成为当前项目 **唯一允许使用的底层探测核心来源**。
3. 当前项目的所有探测调用，最终都必须走这份打包进来的代码。
4. **禁止 AI 新写任何 ICMP、TCP、UDP、HTTP、DNS 的底层探测实现。**

### 固定落地方式

为了避免路径歧义，这次直接把策略写死为：

1. 把外部项目完整放入：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\vendor\Network-Monitoring-Tools`
2. 当前项目继续保留：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools`
3. 但 `agent\network_tools` 不再允许承载新的底层实现；它只允许做**极薄的一层转发或兼容包装**，把调用明确导向 `agent\vendor\Network-Monitoring-Tools`

这样做的原因是：

1. `vendor` 目录负责承载“完整原始来源”
2. `network_tools` 目录负责兼容当前项目既有 import 路径
3. 上层 `probes` 和其他调用方不需要同时大面积改路径

### 对 `vendor` 目录的硬约束

`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\vendor\Network-Monitoring-Tools` 视为**上游镜像区**。

AI Agent 对这部分代码的权限只有两种：

1. 复制进入当前项目
2. 做最小必要兼容修改

禁止：

1. 把它改造成另一套本地重写版本
2. 删除主要目录后再自己重写同名实现
3. 用“参考上游”替代“真实使用上游代码”

如果必须修改 `vendor` 里的代码，你必须满足下面三个条件：

1. 适配层无法解决
2. 修改是最小必要补丁
3. 你能明确说明修改原因、文件路径和兼容目的

---

## 2. 逐文件修改清单

本节替代“任务 A/B/C”的抽象写法。你必须按下面的文件清单执行，优先级从上到下。

### 2.1 必须新增的目录

#### 文件或目录：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\vendor\Network-Monitoring-Tools`

必须完成：

1. 把 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的完整内容复制到这里。
2. 保留上游目录结构，不允许删减为只剩少数文件。
3. 复制后应至少能看到：`icmp_ping`、`tcp_ping`、`udp_ping`、`curl_ping`、`dns_lookup`。

禁止：

1. 只复制目录名不复制实现。
2. 只复制其中一部分协议。
3. 复制后再用本仓库自写实现覆盖上游代码。

完成标准：

1. `agent\vendor\Network-Monitoring-Tools` 成为当前项目内真实存在的完整 vendor 副本。

### 2.2 必须修改的 network_tools 入口文件

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools\icmp_ping\__init__.py`

必须完成：

1. 删除当前仓内自写 ICMP 探测实现。
2. 改为从 `agent\vendor\Network-Monitoring-Tools` 导入或转发到真实 ICMP 实现。
3. 保持当前项目对外可用的调用入口稳定。

禁止：

1. 继续保留 `subprocess + ping` 的本地自写探测逻辑。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools\tcp_ping\__init__.py`

必须完成：

1. 删除当前仓内自写 TCP 探测实现。
2. 改为从 `agent\vendor\Network-Monitoring-Tools` 导入或转发到真实 TCP 实现。
3. 保持当前项目调用方不需要重写全部 import 路径。

禁止：

1. 继续保留本地 `socket.create_connection` 自写 TCP 探测主体。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools\udp_ping\__init__.py`

必须完成：

1. 删除当前仓内自写 UDP 探测实现。
2. 改为从 `agent\vendor\Network-Monitoring-Tools` 导入或转发到真实 UDP 实现。

禁止：

1. 继续保留本地 UDP 探测主逻辑。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools\curl_ping\__init__.py`

必须完成：

1. 删除当前仓内自写 HTTP/HTTPS 探测实现。
2. 改为从 `agent\vendor\Network-Monitoring-Tools` 导入或转发到真实 `curl_ping` 实现。

禁止：

1. 继续保留本地 `curl` 或 `requests` 探测主体。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\network_tools\dns_lookup\__init__.py`

必须完成：

1. 删除当前仓内自写 DNS 探测实现。
2. 改为从 `agent\vendor\Network-Monitoring-Tools` 导入或转发到真实 `dns_lookup` 实现。

禁止：

1. 继续保留本地 `dig` 或 `nslookup` 探测主体。

#### 对以上五个 network_tools 文件的统一完成标准

1. 这些文件只承担稳定入口、导入转发、最小兼容包装。
2. 这些文件中不再保留新的底层探测算法。
3. 运行时实际探测实现来源指向 `agent\vendor\Network-Monitoring-Tools`。

### 2.3 必须核对和必要时修改的 probe 基类文件

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\base.py`

必须完成：

1. 保持 `ProbeResult` 作为唯一统一返回结构。
2. 如果 vendor 引入后发现缺少上层必须字段，只允许在这里做统一结构补充。
3. 不允许各协议自己扩展一套单独返回结构绕开 `ProbeResult`。

完成标准：

1. 所有 probe 的 `probe()` 都能返回 `ProbeResult`。

### 2.4 必须修改的 probe 文件

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\icmp_probe.py`

必须完成：

1. `probe()` 只调用 `agent\network_tools\icmp_ping` 的稳定入口。
2. `probe()` 只做参数传递和 `ProbeResult` 映射。
3. 不在该文件里重新实现 ICMP 探测。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\tcp_probe.py`

必须完成：

1. `probe()` 只调用 `agent\network_tools\tcp_ping` 的稳定入口。
2. `probe()` 只做参数传递和 `ProbeResult` 映射。
3. 修正 `self_test()`，不再只是 `hasattr(socket, 'create_connection')`。
4. `self_test()` 修正后仍然必须满足“失败不阻塞 Agent 启动”。

禁止：

1. 在该文件里重新写 TCP 探测主体。
2. 用不稳定的外网目标做强依赖自检。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\udp_probe.py`

必须完成：

1. 保持当前 `self_test()` 的 `nc` 判定逻辑不被改坏。
2. `probe()` 只调用 `agent\network_tools\udp_ping` 的稳定入口。
3. `probe()` 只做参数传递和 `ProbeResult` 映射。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\http_probe.py`

必须完成：

1. `probe()` 只调用 `agent\network_tools\curl_ping` 的稳定入口。
2. `probe()` 只做参数传递和 `ProbeResult` 映射。
3. 不在该文件里保留新的 HTTP 探测主体。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\dns_probe.py`

必须完成：

1. `probe()` 只调用 `agent\network_tools\dns_lookup` 的稳定入口。
2. `probe()` 只做参数传递和 `ProbeResult` 映射。
3. 不在该文件里保留新的 DNS 探测主体。

#### 对以上五个 probe 文件的统一完成标准

1. 只做适配层，不做底层探测实现。
2. 最终返回 `ProbeResult`。
3. 保持协议注册逻辑可用。

### 2.5 建议核对的安装与引用链路文件

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\scripts\install-agent.sh`

必须核对：

1. 打包后的 agent 部署产物是否会包含 `agent\vendor\Network-Monitoring-Tools`。
2. 不允许出现本地开发环境能跑、安装后 vendor 缺失的情况。

#### 文件：`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\server\api\__init__.py`

必须核对：

1. `/api/agent-package.tar.gz` 打包逻辑是否会把新增的 `agent\vendor\Network-Monitoring-Tools` 一并打进 tar 包。

如果不会，必须修正。

---

## 3. 术语硬定义：什么叫“适配层”

### 3.1 适配层的定义

在本项目里，`agent\probes\*.py` 的“适配层”只允许做以下四类事情：

1. 调用 vendor 探测核心
2. 把当前项目的入参转换成 vendor 函数需要的参数格式
3. 把 vendor 返回结果转换成当前项目统一的 `ProbeResult`
4. 提供协议名、自检接口、注册逻辑

### 3.2 适配层禁止做的事情

`agent\probes\*.py` 禁止做下面这些事：

1. 自己实现真实测量逻辑
2. 重新写 socket、subprocess、requests、curl、dig、nslookup、ping 的核心探测流程
3. 在 probe 文件里堆协议计算细节，导致它变成第二套底层实现

### 3.3 适配层长什么样，直接按这个模式写

```python
class TCPProbe(BaseProbe):
   def protocol_name(self) -> str:
      return 'tcp'

   def self_test(self) -> bool:
      # 这里只做能力发现，不做正式探测逻辑
      ...

   def self_test_reason(self):
      ...

   def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
      vendor_result = vendor_tcp_ping(target=target, port=port or 80, timeout=timeout)
      return ProbeResult(
         success=vendor_result.success,
         latency=vendor_result.latency,
         tcp_time=vendor_result.latency,
         error=vendor_result.error,
      )
```

上面这个模式里的关键点是：

1. `probe()` 本身不写探测算法
2. `probe()` 只调用 vendor 函数
3. `probe()` 只负责参数传递和结果映射

只要超过这个范围，就不是适配层。

---

## 4. 术语硬定义：什么叫“返回值归一化”

### 4.1 返回值归一化的定义

“返回值归一化”指的是：

**无论底层 vendor 代码各协议返回什么结构，到了 `agent\probes\*.py` 这一层，最终都必须被转换成同一个统一结构：`agent\probes\base.py` 里的 `ProbeResult`。**

当前统一结构已经真实存在于：

`D:\wingsrabbit-ovo\NetworkStatus-Rabbit-NG\agent\probes\base.py`

字段如下：

1. `success`
2. `latency`
3. `packet_loss`
4. `jitter`
5. `status_code`
6. `dns_time`
7. `tcp_time`
8. `tls_time`
9. `ttfb`
10. `total_time`
11. `resolved_ip`
12. `error`

### 4.2 归一化的硬规则

你必须严格遵守下面这些规则：

1. 所有 probe 的 `probe()` 最终返回类型必须是 `ProbeResult`
2. 底层返回里存在的指标，映射到对应字段
3. 底层没有的指标，填 `None`
4. 失败时必须有明确的 `success=False`
5. 失败原因尽量进入 `error`
6. 不允许每个协议返回一套自己发明的 dict 结构

### 4.3 归一化不是抽象概念，直接按下面这些例子执行

#### ICMP 例子

如果 vendor 返回：

1. `success`
2. `latency`
3. `packet_loss`
4. `error`

那就归一化成：

```python
return ProbeResult(
   success=r.success,
   latency=r.latency,
   packet_loss=r.packet_loss,
   error=r.error,
)
```

#### TCP 例子

如果 vendor 返回：

1. `success`
2. `latency`
3. `error`

那就归一化成：

```python
return ProbeResult(
   success=r.success,
   latency=r.latency,
   tcp_time=r.latency,
   error=r.error,
)
```

#### HTTP 例子

如果 vendor 返回：

1. `success`
2. `status_code`
3. `dns_time`
4. `tcp_time`
5. `tls_time`
6. `ttfb`
7. `total_time`
8. `resolved_ip`
9. `error`

那就归一化成：

```python
return ProbeResult(
   success=r.success,
   latency=r.total_time,
   status_code=r.status_code,
   dns_time=r.dns_time,
   tcp_time=r.tcp_time,
   tls_time=r.tls_time,
   ttfb=r.ttfb,
   total_time=r.total_time,
   resolved_ip=r.resolved_ip,
   error=r.error,
)
```

#### DNS 例子

如果 vendor 返回：

1. `success`
2. `latency`
3. `resolved_ip`
4. `error`

那就归一化成：

```python
return ProbeResult(
   success=r.success,
   latency=r.latency,
   dns_time=r.latency,
   resolved_ip=r.resolved_ip,
   error=r.error,
)
```

### 4.4 什么不叫归一化

下面这些写法都不合格：

1. 某个 probe 返回自定义 dict，另一个返回 dataclass，第三个返回 tuple
2. HTTP 返回一套字段名，DNS 返回另一套字段名，上层自己猜
3. probe 层直接把 vendor 原始对象往上传，不做统一转换

---

## 5. 文件级操作规则

### 5.1 `agent\vendor\Network-Monitoring-Tools`

必须新增并完整导入外部探测核心。

### 5.2 `agent\network_tools\*`

允许做的事：

1. import vendor 代码
2. 保留稳定的项目内调用路径
3. 做最薄兼容转发

禁止做的事：

1. 继续保留自写探测实现
2. 新写新的底层探测算法

### 5.3 `agent\probes\*`

允许做的事：

1. 协议名声明
2. 自检
3. 调用 `agent\network_tools` 或直接调 vendor 稳定入口
4. 结果归一化到 `ProbeResult`
5. 注册协议

禁止做的事：

1. 自己发请求、建 socket、跑系统命令来替代 vendor 正式探测流程
2. 自己重新实现协议测量核心

---

## 6. 明确不要动的内容

以下问题已经确认修复完成，除非被剩余修复真实阻塞，否则不要重新打开：

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

---

## 7. 开工前必须先核查的事项

在正式改代码前，必须逐项核查并确认：

1. `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 下五类协议真实入口文件和当前项目入口如何映射
2. 当前 `agent\network_tools\*` 与 vendor 同名目录之间，哪些可直接替换，哪些需要薄兼容层
3. 当前 `agent\probes\base.py` 的 `ProbeResult` 是否覆盖五类协议对上层所需的字段
4. TCP 自检修正后，是否仍满足“失败不阻塞启动”

---

## 8. 完工验收标准

全部完成后，必须同时满足：

1. 当前项目运行时使用的五类协议底层探测核心，真实来源来自 `D:\wingsrabbit-ovo\Network-Monitoring-Tools` 的完整打包副本
2. `agent\probes\*.py` 全部符合本文件第 3 节对“适配层”的定义
3. `agent\probes\*.py` 全部符合本文件第 4 节对“返回值归一化”的定义
4. `agent\probes\tcp_probe.py` 的 `self_test()` 不再只是 `hasattr()`
5. Agent 启动链路仍满足“单协议自检失败不阻塞整体启动”
6. 本文件第 6 节列出的已完成模块没有被重新改坏

---

## 9. AI Agent 最终输出要求

完成修改后，你必须明确输出：

1. 你改了哪些文件
2. 每个文件为什么要改
3. 哪些改动用于把外部探测核心完整 vendor 进入 `agent`
4. 哪些改动用于让 `probes` 真正变成适配层
5. 哪些改动用于做 `ProbeResult` 归一化
6. 哪些改动用于修复 TCP 自检
7. 你如何证明当前运行时探测核心真实来自 `D:\wingsrabbit-ovo\Network-Monitoring-Tools`，而不是继续停留在“看起来像上游”的状态

---

## 10. 三轮迭代结果

### 第 1 轮

删除了不帮助 AI Agent 改项目的评审性文案，只保留真实路径、真实问题、真实限制。

### 第 2 轮

把“完整打包进 agent，禁止 AI 自写底层探测实现”写成唯一允许采用的总体策略，消除了“来源对齐”一词的歧义。

### 第 3 轮

把“适配层”“返回值归一化”全部改成硬定义、禁止项和直接可照抄的例子，消除了“AI Agent 可能听不懂”的不确定性。
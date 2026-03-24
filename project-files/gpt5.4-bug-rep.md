# NetworkStatus-Rabbit Bug Report

任务名称：debug NetworkStatus-Rabbit

报告时间：2026-03-24

结论级别：高置信度

---

## 1. 问题摘要

当前线上现象是：

1. Dashboard 卡片页可以正常看到任务最新延迟/丢包数据。
2. 点击进入任务详情页后，统计卡全部为空，数据点数为 0。
3. 图表区域没有正常曲线，底部出现 `Invalid Date`。

结合当前仓库代码，问题不是单点故障，而是两处相互叠加的缺陷：

1. Agent 上报的 `timestamp` 格式错误，导致时序数据大概率没有被正确写入 InfluxDB。
2. 任务详情页消费实时 WebSocket 数据时，前后端消息结构不一致，导致前端拿不到正确的 `latency/packet_loss/jitter` 字段，并把非法时间直接送进图表。

这两处问题叠加后，就会形成你现在看到的完整症状：

1. Dashboard 正常，因为它主要看的是服务端内存中的最新结果缓存。
2. Detail 空白，因为它主要依赖 InfluxDB 历史数据查询。
3. Detail 页面出现 `Invalid Date`，因为实时推送带来的时间字段格式不合法，且消息结构不匹配。

---

## 2. 根因一：Agent 时间戳格式错误

### 2.1 证据

文件：agent/ws_client.py

当前实现：

```python
payload = {
    'result_id': result_id,
    'task_id': task_id,
    'timestamp': timestamp.isoformat() + 'Z',
    'protocol': protocol,
    'metrics': result.to_dict(),
}
```

而 `timestamp` 的来源在 agent/scheduler.py：

```python
now = datetime.now(timezone.utc)
```

这里的 `now` 已经是带时区的 UTC 时间。Python 对这种对象调用 `isoformat()`，通常会得到：

```text
2026-03-24T12:34:56.789123+00:00
```

代码又额外拼接了一个 `Z`，结果会变成：

```text
2026-03-24T12:34:56.789123+00:00Z
```

这不是合法的标准 RFC3339/ISO8601 UTC 表达。

### 2.2 为什么这会造成“详情页无数据”

服务端接收到 agent 结果后，会在 server/ws/agent_handler.py 中调用：

```python
influx_service.write_probe_result({... 'timestamp': data.get('timestamp'), ...})
```

再进入 server/services/influx_service.py：

```python
if ts:
    if isinstance(ts, str):
        point = point.time(ts, WritePrecision.S)
```

如果传入的是 `2026-03-24T12:34:56.789123+00:00Z` 这种非法时间字符串，Influx 写入极大概率失败。

而 server/ws/agent_handler.py 对写入异常的处理是：

```python
except Exception as e:
    logger.error(f"Failed to write probe result: {e}")
```

也就是说：

1. 写入失败不会阻断后续流程。
2. Dashboard 仍然会继续收到“最新结果缓存”。
3. 但 Detail 页查询 Influx 历史数据时就是空的。

这与线上现象完全吻合：

1. Dashboard 有最新值。
2. Detail `平均延迟/P95/平均丢包/数据点数` 全空。
3. 图表也没有历史曲线。

### 2.3 影响范围

影响所有任务详情页，不区分协议。只要数据写入链路经过这段代码，就会中招。

---

## 3. 根因二：任务详情页实时消息结构不一致

### 3.1 前端期待的数据结构

文件：web/src/views/TaskDetailView.vue

前端把历史接口返回和实时推送都当成 `ProbeResult` 使用：

```ts
const result = data.result as ProbeResult
points.value.push(result)
```

`ProbeResult` 的定义在 web/src/types/index.ts：

```ts
export interface ProbeResult {
  timestamp: string
  latency: number | null
  packet_loss: number | null
  jitter: number | null
  success: boolean | null
  ...
}
```

也就是说，详情页期待的是“扁平结构”：

```json
{
  "timestamp": "...",
  "latency": 12.3,
  "packet_loss": 0,
  "jitter": 1.2,
  "success": true
}
```

### 3.2 后端实际推送的数据结构

文件：server/ws/dashboard_handler.py

```python
def push_task_detail(task_id, result_data):
    socketio.emit('dashboard_task_detail', {
        'task_id': task_id,
        'result': result_data,
    }, room=room, namespace='/dashboard')
```

而 `result_data` 来自 server/ws/agent_handler.py：

```python
push_task_detail(task_id, data)
```

这里传进去的 `data` 是 agent 原始包，结构是：

```json
{
  "result_id": "...",
  "task_id": "...",
  "timestamp": "2026-03-24T12:34:56.789123+00:00Z",
  "protocol": "icmp",
  "metrics": {
    "latency": 0.2,
    "packet_loss": 0,
    "jitter": null,
    "success": true
  }
}
```

注意这里的 `latency/packet_loss/jitter/success` 都在 `metrics` 里面，不在顶层。

### 3.3 为什么这会造成 `Invalid Date` 和图表异常

文件：web/src/views/TaskDetailView.vue

图表直接读取：

```ts
const times = points.value.map((p) => dayjs(p.timestamp).format('HH:mm:ss'))
const latencies = points.value.map((p) => p.latency)
const losses = points.value.map((p) => p.packet_loss)
const jitters = points.value.map((p) => p.jitter)
```

问题在于：

1. 实时推送里的 `timestamp` 是非法格式 `+00:00Z`，`dayjs()` 解析后会得到 `Invalid Date`。
2. 实时推送里的 `latency/packet_loss/jitter` 不在顶层，前端读取到的是 `undefined`。

所以你截图中的现象正好成立：

1. 横轴出现 `Invalid Date`。
2. 图上没有有效折线。
3. Detail 页面即使有实时消息，也无法正确展示。

---

## 4. 为什么 Dashboard 卡片页看起来又是正常的

这是因为 Dashboard 和 Detail 走的不是同一条数据链路。

Dashboard 列表页主要依赖：

1. server/ws/agent_handler.py 中的 `_latest_results` 内存缓存。
2. server/api/data.py 的 `/api/data/dashboard` 返回值。
3. server/app.py 每秒推送的 `dashboard_probe_snapshot`。

这条链路并不依赖 Influx 查询结果是否成功落盘，也不展示时间轴，所以即使历史写入失败，首页卡片依然能看到“最新延迟”。

Detail 页则不同：

1. 首屏加载调用 `/api/data/task/<task_id>` 和 `/api/data/task/<task_id>/stats`。
2. 这两个接口都直接查 InfluxDB。
3. 如果 Influx 没写进去，首屏就是空。
4. 后续再叠加错误的实时消息结构，就只会出现 `Invalid Date` 和空图。

---

## 5. 结论归纳

本次问题的核心根因链如下：

1. Agent 生成了非法 UTC 时间字符串：`timestamp.isoformat() + 'Z'`。
2. 服务端把这个非法时间直接用于 Influx 写入。
3. 写入失败后仅记日志，不阻断 Dashboard 内存态更新。
4. 所以首页卡片仍显示“正常运行”。
5. Detail 页查询 Influx 历史数据时为空，因此统计卡和图表为空。
6. 同时，Detail 页订阅到的实时消息结构又与前端 `ProbeResult` 类型不一致。
7. 非法时间继续触发 `Invalid Date`，嵌套 `metrics` 又让折线值变成 `undefined`。

所以这不是“前端图表自己坏了”，而是“存储链路 + 实时消息契约”同时有问题。

---

## 6. 建议修复顺序

### P0：先修时间戳格式

建议把 agent 侧时间序列化改成合法 UTC 形式，二选一即可：

方案 A：直接使用 aware datetime 的标准输出，不再拼 `Z`

```python
'timestamp': timestamp.isoformat(),
```

方案 B：输出标准 `Z` 结尾格式，但先把 `+00:00` 替换掉

```python
'timestamp': timestamp.isoformat().replace('+00:00', 'Z'),
```

这一项不修，Detail 页历史数据会持续为空。

### P0：统一 `dashboard_task_detail` 消息结构

后端推给前端的 `result` 必须改成与 `ProbeResult` 一致的扁平结构，例如：

```json
{
  "task_id": "...",
  "result": {
    "timestamp": "2026-03-24T12:34:56.789123Z",
    "latency": 0.2,
    "packet_loss": 0,
    "jitter": null,
    "success": true,
    "status_code": null,
    "dns_time": null,
    "tcp_time": null,
    "tls_time": null,
    "ttfb": null,
    "total_time": null,
    "resolved_ip": null
  }
}
```

不要再直接把 agent 原始 payload 透传给详情页。

### P1：补一条写入失败的可观测性

当前写 Influx 失败只是记日志，业务层没有任何显式告警。建议至少增加：

1. 写入失败计数。
2. 最近一次写入错误摘要。
3. 面板或日志中可快速识别“Dashboard 有数据但 Detail 无历史”的状态。

---

## 7. 建议验证步骤

修复后建议按以下顺序验证：

1. 新建一个 ICMP 任务。
2. 观察 Dashboard 卡片是否继续有实时数据。
3. 进入 Detail 页面，确认首屏 `数据点数` 大于 0。
4. 确认 `平均延迟/P95/平均丢包` 正常显示。
5. 确认图表横轴不再出现 `Invalid Date`。
6. 再观察 1 到 2 分钟，确认实时曲线持续追加，不再出现空点或 undefined。

---

## 8. 本次报告的边界说明

本报告基于以下证据形成：

1. 当前仓库源码静态分析。
2. 你提供的线上页面截图。
3. 前后端数据结构和调用链逐段核对。

当前环境的命令策略禁止直接使用 `Invoke-WebRequest`/`curl` 对线上接口做补充抓包，因此没有附上线上 API 原始响应样本；但从代码路径和现象对照来看，以上结论已经足够闭环，且置信度高。

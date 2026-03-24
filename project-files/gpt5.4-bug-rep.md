# NetworkStatus-Rabbit Bug Report

任务名称：debug NetworkStatus-Rabbit

当前文档版本：v0.124

最后整理时间：2026-03-24

文档原则：

1. 当前状态里只保留未解决问题。
2. 每个问题都必须包含代码依据和可执行的实现思路。
3. 已解决内容只放在对应版本的“已完成任务”中，不再回放全文。

---

## 1. 当前状态

### v0.124 当前问题

1. 图表发生数据更新时会重置缩放状态，局部查看被强行打回全量视图。
现象：用户手动拖动 `dataZoom` 进入局部区间后，只要有新数据到达或页面定时刷新，缩放就被重置。这会让详情页在观察某个异常片段时几乎不可用。
代码依据：
1. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 的 `updateChart()` 每次都会重新计算 `now = Date.now()`，然后把 `xAxis.min/max` 重设为 `now - windowMs` 与 `now`。
2. 同一处调用 `chart.value.setOption(..., true)`，第二个参数是 `notMerge=true`，会把现有的 `dataZoom` 状态整体覆盖掉。
3. 当前页面只维护了 `isZoomed` 布尔值，没有真正记录用户当前缩放区间，例如 `startValue/endValue` 或可见时间窗。
实现思路：
1. 不要在每次刷新时用 `notMerge=true` 整体重建图表；更新数据序列时应优先走局部 `setOption` 合并。
2. 在 `datazoom` 事件里记录真实可见区间，至少保存 `startValue/endValue`，而不是只保存一个布尔值。
3. 当用户处于缩放态时，实时更新只能更新 `series.data`，不能覆盖 `xAxis.min/max`；只有用户点击“重置缩放”或切换 range 时，才恢复基础窗口。
4. 如果要兼顾“原始窗口继续向前推进”和“用户局部观察不被打断”，可以维护两套窗口：基础窗口持续滑动，当前可见窗口在缩放态下冻结，退出缩放后再回到基础窗口。
影响：目前详情页的缩放功能名义上存在，但一旦有实时数据就失效，无法支撑对异常片段进行持续观察。
验收标准：缩放后即便新数据到达、stats 刷新或定时拉取发生，图表仍保持用户当前局部视图；只有手动重置或切换 range 才回到全量窗口。

2. `icmp` 的“1 秒任务却 3 到 4 秒才更新一次”不是前端问题，而是 probe 实现本身和 `tcp` 不是同一种采样语义。
现象：`tcp` 测试可以做到接近 1 秒 1 条，但 `icmp` 在同样配置下变成 3 到 4 秒才出 1 条结果，看起来像链路更新模块坏了，实际是协议实现不一致。
代码依据：
1. [agent/scheduler.py](agent/scheduler.py) 当前 `_task_loop()` 已经是固定节拍模型：`next_run += interval` 后按剩余时间等待，所以“执行完再睡 interval”的老问题在当前代码里已经不是主因。
2. [agent/probes/tcp_probe.py](agent/probes/tcp_probe.py) 每轮只做一次 `socket.create_connection()`，一次任务循环产出一条结果。
3. [agent/probes/icmp_probe.py](agent/probes/icmp_probe.py) 当前却写死了 `count = 4`，Windows 走 `ping -n 4`，Linux 走 `ping -c 4`。这意味着一次“ICMP 探测结果”内部其实包含 4 个 ping 子样本，Windows 默认子样本之间还会有约 1 秒间隔，所以单轮天然会拖到 3 到 4 秒。
4. [agent/probes/udp_probe.py](agent/probes/udp_probe.py)、[agent/probes/http_probe.py](agent/probes/http_probe.py)、[agent/probes/dns_probe.py](agent/probes/dns_probe.py) 当前都属于“一轮任务做一次探测并回一条结果”的模式；所谓 `ssl` 在当前代码里并不是独立协议，而是 [agent/probes/http_probe.py](agent/probes/http_probe.py) 中 `https` URL 的同一条请求链路。
实现思路：
1. 如果产品语义要求“任务 interval=1 就应接近每秒 1 条结果”，那 `icmp` 不能继续保留 `count=4` 的批量 ping 语义，应改成和 `tcp/udp/http/dns` 一样的单次探测模型，即每轮只发 1 个 echo request。
2. `icmp` 现有的 `packet_loss` 和 `jitter` 不能再靠“一次命令里打 4 个包”来算，应该改成基于最近 N 条单次结果在服务端或前端窗口内再计算。否则 `icmp` 会永远和其他协议不在一个节拍体系里。
3. `udp/http(dns/tls)/dns` 不需要“抄 tcp 模块”，因为它们本来就是单次采样；真正要统一的是“每个任务循环只产出一条基础样本”的设计约束。
影响：当前 `icmp` 的结果频率、数据点数、丢包/抖动语义都和其他协议不一致，用户会误以为只有 `icmp` 有更新故障。
验收标准：`interval=1` 的 `icmp` 任务在正常网络下应接近 1 秒 1 条结果；各协议统一遵守“一次调度循环 = 一条基础样本”的规则。

3. 当前时间窗口直接贴着 `now` 画到最右侧，没有给探测完成和超时判定预留会合区，天然会制造“最后几秒像丢点”的假象。
现象：页面当前把最右边界直接对齐当前时间，导致最近几秒内那些“还在探测中”或“尚未到达超时阈值”的样本也被视作窗口内应出现的数据。用户看到的效果就是尾部像缺点、掉点，统计也会被误读。
代码依据：
1. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 当前 `updateChart()` 固定使用 `xAxis.max = Date.now()`，没有任何安全尾巴。
2. [server/api/data.py](server/api/data.py) 当前 `task_stats()` 计算 `window_end` 和 `expected_probes` 也是直接用 `now`，没有考虑任务 `timeout` 或数据会合延迟。
3. [project-files/PROJECT.md](project-files/PROJECT.md) 的任务模型里 `timeout` 明确定义为探测超时时间；在这个语义下，尾部未完成样本在超时前本来就不应被当作“缺失结果”。
实现思路：
1. 详情页的展示窗口右边界不应直接取当前墙钟时间，而应取“当前时间减去安全尾巴”。按你举的例子，当前更合理的是把尾巴至少设为任务 `timeout` 秒，默认就是 10 秒；如果只写死 5 秒，会和“超过 10 秒才算超时”这条规则冲突。
2. 前端图表、顶部统计、`expected_probes` 的理论计数都应使用同一套 `effective_window_end`，否则图表和统计会互相打架。
3. 原始视图下新结果可以先进本地 buffer，等其时间戳进入“可见窗口”后再并入图表，这就是允许数据会合，而不是把还没结束的采样硬算成丢失。
影响：如果不做安全尾巴，最近一段时间的曲线和数据点数永远偏小，用户会把“尚未完成”误认成“系统漏写”或“探测失败”。
验收标准：当当前时间为 13:58:00 时，图表与统计的最右边界不直接落在 13:58:00，而是落在统一定义的安全会合点；尾部不再因为尚未完成的探测而表现成假性掉点。

4. 时间范围与刷新粒度没有按 Project 6.2 和 10.3 实现，前端目前少了 `3d`、`14d`，刷新节拍也不是按秒/分钟/小时边界对齐。
现象：用户现在明确要求的范围是：`30m`、`1h`、`6h`、`24h`、`3d`、`7d`、`14d`、`30d`。但当前详情页只有 `30m/1h/6h/24h/7d/30d`，少了 `3d` 和 `14d`。同时，刷新节奏现在是 `10s/15s/60s/300s` 这种任意轮询，不是“30 分钟到 24 小时按秒、3 天到 7 天按分钟、14 天到 30 天按小时”的规格。
代码依据：
1. [project-files/PROJECT.md](project-files/PROJECT.md) 的 6.2 已经写死 bucket 语义：`24h -> raw`，`3d/7d -> agg_1m`，`14d/30d -> agg_1h`。
2. [project-files/PROJECT.md](project-files/PROJECT.md) 的 10.3 布局描述里也明确列出了 `3d` 与 `14d` 两档范围。
3. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 现在 `rangeOptions` 缺少 `3d`、`14d`；`refreshInterval()` 仍然返回 `10_000/15_000/60_000/300_000`；`xAxisLabelFormat` 也没有为 `3d`、`14d` 单独定义粒度。
4. [server/services/influx_service.py](server/services/influx_service.py) 的 `_select_bucket()` 实际已经支持这两档区间：`<=24h` 走 raw，`<=7d` 走 1m，其他走 1h。也就是说后端 bucket 选择大体够用，主要缺口在前端范围与刷新策略。
实现思路：
1. 前端 range 选项应补齐为 8 档：`30m/1h/6h/24h/3d/7d/14d/30d`。
2. 刷新逻辑不要再用随意的固定轮询，而应改成“对齐边界”的调度：
	- `30m ~ 24h`：按秒边界刷新；
	- `3d ~ 7d`：按分钟边界刷新；
	- `14d ~ 30d`：按小时边界刷新。
3. range 切换后，图表标签格式、tooltip 时间格式、理论点数计算、bucket 选择都要跟着统一切换。
4. 原始视图仍可继续吃 websocket 增量，但秒级视图的整页重算也应落在秒边界，而不是任意时刻触发。
影响：当前实现和工程规格脱节，用户看到的不是“bucket 粒度视图”，而是“不稳定轮询 + 缺失范围”的混合行为。
验收标准：详情页范围完整支持 8 档；`30m~24h` 视图以秒为刷新节点，`3d~7d` 以分钟为刷新节点，`14d~30d` 以小时为刷新节点；bucket 选择与 Project 6.2 一致。

5. `数据点数` 需要从“原始 total_probes”升级为“实际记录数 / 理论记录数（基于有效窗口）”，否则无法判断是正常会合、协议语义差异，还是实际掉点。
现象：现在页面虽然已经显示 `total_probes / expected_probes`，但这个理论值还是按“当前时间直达右边界”的旧窗口算出来的，一旦引入安全尾巴或新增 `3d/14d` 粒度，这个数字就会继续失真。
代码依据：
1. [server/api/data.py](server/api/data.py) 当前 `expected_probes = range_seconds // task.interval`，它没有使用“有效窗口终点”，也没有区分聚合 bucket 下的分钟级/小时级统计语义。
2. [web/src/views/TaskDetailView.vue](web/src/views/TaskDetailView.vue) 当前虽然展示了 `stats.total_probes / stats.expected_probes`，但没有告诉用户理论值是按什么窗口、什么粒度算的。
实现思路：
1. 原始视图下，理论记录数应基于“有效窗口长度 / task.interval”计算，窗口终点取会合后的 `effective_window_end`。
2. 聚合视图下，不应再沿用“按探测 interval 算理论秒级点数”的展示，而应明确展示“已聚合桶数 / 理论桶数”，否则 `3d/7d/14d/30d` 会把 bucket 语义和原始样本语义混在一起。
3. 详情页文案建议明确区分：`原始样本数`、`理论样本数`、`聚合桶数`，避免用户把分钟桶数误读成秒级掉点。
影响：如果不重定义这个指标，后续即便补了会合区和新 range，页面仍然会不断制造“少点了”的误报。
验收标准：不同范围下的数据点指标都能解释清楚“为什么是这个数”，用户能分辨当前看到的是原始样本缺失、聚合桶数量，还是正常会合延迟。

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

---



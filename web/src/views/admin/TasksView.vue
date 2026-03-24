<script setup lang="ts">
import { onMounted, ref, h, computed, watch } from 'vue'
import {
  NDataTable, NButton, NSpace, NModal, NForm, NFormItem, NInput,
  NSelect, NInputNumber, NTag, NPopconfirm, NAlert, useMessage, NPageHeader
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { getTasks, createTask, updateTask, deleteTask, toggleTask } from '@/api/tasks'
import { getNodes } from '@/api/nodes'
import type { ProbeTask, Node } from '@/types'

const message = useMessage()
const tasks = ref<ProbeTask[]>([])
const nodes = ref<Node[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const showForm = ref(false)
const isEdit = ref(false)
const editingId = ref('')

const defaultForm = (): Partial<ProbeTask> => ({
  name: '',
  source_node_id: '',
  protocol: 'icmp',
  target_type: 'external',
  target_node_id: null,
  target_address: '',
  target_port: null,
  interval: 5,
  timeout: 10,
  alert_latency_threshold: null,
  alert_loss_threshold: null,
  alert_fail_count: null,
  alert_eval_window: 5,
  alert_trigger_count: 3,
  alert_recovery_count: 3,
  alert_cooldown_seconds: 300,
})

const form = ref<Partial<ProbeTask>>(defaultForm())

const protocolOptions = [
  { label: 'ICMP', value: 'icmp' },
  { label: 'TCP', value: 'tcp' },
  { label: 'UDP', value: 'udp' },
  { label: 'HTTP', value: 'http' },
  { label: 'DNS', value: 'dns' },
]

const targetTypeOptions = [
  { label: '外部目标', value: 'external' },
  { label: '内部节点', value: 'internal' },
]

const nodeOptions = computed(() =>
  nodes.value.map((n) => ({ label: `${n.name} (${n.id.slice(0, 8)})`, value: n.id }))
)

const needsPort = computed(() => ['tcp', 'udp'].includes(form.value.protocol || ''))

const protocolWarning = ref<string | null>(null)

watch(
  [() => form.value.source_node_id, () => form.value.protocol],
  ([nodeId, protocol]) => {
    if (!nodeId || !protocol) {
      protocolWarning.value = null
      return
    }
    const node = nodes.value.find((n) => n.id === nodeId)
    if (!node || !node.capabilities) {
      protocolWarning.value = null
      return
    }
    const supported = node.capabilities.protocols || []
    if (supported.includes(protocol)) {
      protocolWarning.value = null
    } else {
      const reason = node.capabilities.unsupported_reasons?.[protocol] || '不支持'
      protocolWarning.value = `源节点「${node.name}」不支持 ${protocol.toUpperCase()} 协议：${reason}`
    }
  },
)

const hasAlert = computed(() =>
  form.value.alert_latency_threshold != null ||
  form.value.alert_loss_threshold != null ||
  form.value.alert_fail_count != null
)

async function fetchData() {
  loading.value = true
  try {
    const [taskRes, nodeRes] = await Promise.all([
      getTasks({ page: page.value, per_page: 20 }),
      getNodes({ per_page: 100 }),
    ])
    tasks.value = taskRes.data.items
    total.value = taskRes.data.pagination.total
    nodes.value = nodeRes.data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  form.value = defaultForm()
  showForm.value = true
}

function openEdit(task: ProbeTask) {
  isEdit.value = true
  editingId.value = task.id
  form.value = { ...task }
  showForm.value = true
}

async function handleSubmit() {
  if (!form.value.name || !form.value.source_node_id) {
    message.warning('请填写必要字段')
    return
  }
  try {
    if (isEdit.value) {
      await updateTask(editingId.value, form.value)
      message.success('更新成功')
    } else {
      await createTask(form.value)
      message.success('创建成功')
    }
    showForm.value = false
    fetchData()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '操作失败')
  }
}

async function handleDelete(id: string) {
  try {
    await deleteTask(id)
    message.success('删除成功')
    fetchData()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '删除失败')
  }
}

async function handleToggle(task: ProbeTask) {
  try {
    await toggleTask(task.id, !task.enabled)
    fetchData()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '操作失败')
  }
}

const columns: DataTableColumns<ProbeTask> = [
  { title: 'ID', key: 'id', width: 220, ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', width: 160 },
  {
    title: '协议', key: 'protocol', width: 80,
    render: (row) => h(NTag, { size: 'small' }, { default: () => row.protocol.toUpperCase() }),
  },
  { title: '源节点', key: 'source_node_id', width: 140, ellipsis: { tooltip: true } },
  { title: '目标', key: 'target_address', width: 200, ellipsis: { tooltip: true } },
  { title: '间隔(s)', key: 'interval', width: 80 },
  {
    title: '启用', key: 'enabled', width: 70,
    render: (row) => h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '是' : '否' }),
  },
  {
    title: '告警', key: 'alert', width: 70,
    render: (row) => {
      const has = row.alert_latency_threshold != null ||
                  row.alert_loss_threshold != null ||
                  row.alert_fail_count != null
      return h(NTag, { type: has ? 'warning' : 'default', size: 'small' }, { default: () => has ? '开' : '关' })
    },
  },
  {
    title: '操作', key: 'actions', width: 220,
    render: (row) => h(NSpace, { size: 4 }, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: row.enabled ? 'warning' : 'success', onClick: () => handleToggle(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除？',
        }),
      ],
    }),
  },
]

onMounted(fetchData)
</script>

<template>
  <div>
    <NPageHeader title="任务管理">
      <template #extra>
        <NButton type="primary" @click="openCreate">添加任务</NButton>
      </template>
    </NPageHeader>

    <NDataTable
      :columns="columns"
      :data="tasks"
      :loading="loading"
      :pagination="{ page, pageSize: 20, itemCount: total, onChange: (p: number) => { page = p; fetchData() } }"
      style="margin-top: 16px"
    />

    <NModal v-model:show="showForm" preset="card" :title="isEdit ? '编辑任务' : '添加任务'" style="width: 600px">
      <NForm label-placement="left" label-width="120">
        <NFormItem label="名称" required>
          <NInput v-model:value="form.name" />
        </NFormItem>
        <NFormItem label="源节点" required>
          <NSelect v-model:value="form.source_node_id" :options="nodeOptions" filterable :disabled="isEdit" />
        </NFormItem>
        <NFormItem label="协议">
          <NSelect v-model:value="form.protocol" :options="protocolOptions" :disabled="isEdit" />
        </NFormItem>
        <NAlert v-if="protocolWarning" type="warning" style="margin-bottom: 16px">
          {{ protocolWarning }}
        </NAlert>
        <NFormItem label="目标类型">
          <NSelect v-model:value="form.target_type" :options="targetTypeOptions" :disabled="isEdit" />
        </NFormItem>
        <NFormItem v-if="form.target_type === 'internal'" label="目标节点">
          <NSelect v-model:value="form.target_node_id" :options="nodeOptions" filterable :disabled="isEdit" />
        </NFormItem>
        <NFormItem v-else label="目标地址">
          <NInput v-model:value="form.target_address" placeholder="IP 或域名" :disabled="isEdit" />
        </NFormItem>
        <NFormItem v-if="needsPort" label="目标端口">
          <NInputNumber v-model:value="form.target_port" :min="1" :max="65535" style="width: 100%" />
        </NFormItem>
        <NFormItem label="间隔(秒)">
          <NInputNumber v-model:value="form.interval" :min="1" :max="60" style="width: 100%" />
        </NFormItem>
        <NFormItem label="超时(秒)">
          <NInputNumber v-model:value="form.timeout" :min="1" :max="30" style="width: 100%" />
        </NFormItem>

        <NFormItem label="延迟阈值 (ms)">
          <NInputNumber v-model:value="form.alert_latency_threshold" :min="0" placeholder="留空则不监控" style="width: 100%" clearable />
        </NFormItem>
        <NFormItem label="丢包率阈值 (%)">
          <NInputNumber v-model:value="form.alert_loss_threshold" :min="0" :max="100" placeholder="留空则不监控" style="width: 100%" clearable />
        </NFormItem>
        <NFormItem label="连续失败次数">
          <NInputNumber v-model:value="form.alert_fail_count" :min="1" placeholder="留空则不监控" style="width: 100%" clearable />
        </NFormItem>
        <template v-if="hasAlert">
          <NFormItem label="评估窗口">
            <NInputNumber v-model:value="form.alert_eval_window" :min="1" style="width: 100%" />
          </NFormItem>
          <NFormItem label="触发次数">
            <NInputNumber v-model:value="form.alert_trigger_count" :min="1" style="width: 100%" />
          </NFormItem>
          <NFormItem label="恢复次数">
            <NInputNumber v-model:value="form.alert_recovery_count" :min="1" style="width: 100%" />
          </NFormItem>
          <NFormItem label="冷却时间(s)">
            <NInputNumber v-model:value="form.alert_cooldown_seconds" :min="0" style="width: 100%" />
          </NFormItem>
        </template>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleSubmit">{{ isEdit ? '保存' : '创建' }}</NButton>
      </template>
    </NModal>
  </div>
</template>

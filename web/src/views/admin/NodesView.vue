<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NModal, NForm, NFormItem, NInput, NTag,
  NPopconfirm, NCode, NTooltip, useMessage, NPageHeader
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { getNodes, createNode, updateNode, deleteNode, getDeployCommand } from '@/api/nodes'
import type { Node } from '@/types'

const message = useMessage()
const nodes = ref<Node[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const showCreate = ref(false)
const showDeploy = ref(false)
const showEdit = ref(false)
const deployScriptCommand = ref('')
const deployDockerCommand = ref('')
const deployDockerListenCommand = ref('')
const createForm = ref({ name: '', label_1: '', label_2: '', label_3: '' })
const editForm = ref<Partial<Node>>({})
const editingId = ref('')

async function fetchNodes() {
  loading.value = true
  try {
    const res = await getNodes({ page: page.value, per_page: 20 })
    nodes.value = res.data.items
    total.value = res.data.pagination.total
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.name) {
    message.warning('请输入节点名称')
    return
  }
  try {
    const res = await createNode(createForm.value)
    const nodeId = res.data.node.id
    showCreate.value = false
    createForm.value = { name: '', label_1: '', label_2: '', label_3: '' }
    fetchNodes()
    // Open deploy dialog with commands
    try {
      const cmdRes = await getDeployCommand(nodeId)
      deployScriptCommand.value = cmdRes.data.script_command
      deployDockerCommand.value = cmdRes.data.docker_command
      deployDockerListenCommand.value = cmdRes.data.docker_command_listen
    } catch { /* ignore */ }
    showDeploy.value = true
    message.success('节点创建成功')
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '创建失败')
  }
}

function openEdit(node: Node) {
  editingId.value = node.id
  editForm.value = {
    name: node.name,
    label_1: node.label_1,
    label_2: node.label_2,
    label_3: node.label_3,
    enabled: node.enabled,
  }
  showEdit.value = true
}

async function handleEdit() {
  try {
    await updateNode(editingId.value, editForm.value)
    showEdit.value = false
    fetchNodes()
    message.success('更新成功')
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '更新失败')
  }
}

async function handleDelete(id: string) {
  try {
    await deleteNode(id)
    fetchNodes()
    message.success('删除成功')
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '删除失败')
  }
}

async function handleToggle(node: Node) {
  try {
    await updateNode(node.id, { enabled: !node.enabled })
    fetchNodes()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '操作失败')
  }
}

async function handleDeploy(id: string) {
  try {
    const res = await getDeployCommand(id)
    deployScriptCommand.value = res.data.script_command
    deployDockerCommand.value = res.data.docker_command
    deployDockerListenCommand.value = res.data.docker_command_listen
    showDeploy.value = true
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '获取失败')
  }
}

const columns: DataTableColumns<Node> = [
  { title: 'ID', key: 'id', width: 220, ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', width: 140 },
  {
    title: '状态', key: 'status', width: 80,
    render: (row) => {
      const map: Record<string, { type: 'success' | 'error' | 'warning' | 'default'; label: string }> = {
        online: { type: 'success', label: '在线' },
        offline: { type: 'error', label: '离线' },
        registered: { type: 'warning', label: '已注册' },
        disabled: { type: 'default', label: '已禁用' },
      }
      const s = map[row.status] || map.offline
      return h(NTag, { type: s.type, size: 'small' }, { default: () => s.label })
    },
  },
  {
    title: '启用', key: 'enabled', width: 80,
    render: (row) => h(NTag, { type: row.enabled ? 'info' : 'default', size: 'small' }, { default: () => row.enabled ? '是' : '否' }),
  },
  { title: '标签1', key: 'label_1', width: 100 },
  { title: '标签2', key: 'label_2', width: 100 },
  { title: '标签3', key: 'label_3', width: 100 },
  { title: '版本', key: 'agent_version', width: 80 },
  { title: 'IP', key: 'public_ip', width: 130 },
  {
    title: '协议支持', key: 'capabilities', width: 380,
    render: (row) => {
      const ALL_PROTOCOLS = ['icmp', 'tcp', 'udp', 'http', 'dns', 'mtr_icmp', 'mtr_tcp', 'mtr_udp']
      /** Protocols that require a listen_port on the target agent for internal probes */
      const PORT_REQUIRED = ['tcp', 'udp']
      const caps = row.capabilities
      const supported = caps?.protocols || []
      const reasons = caps?.unsupported_reasons || {}
      const listenPort = caps?.listen_port
      return h(NSpace, { size: 4 }, {
        default: () => ALL_PROTOCOLS.map((p) => {
          const isSupported = supported.includes(p)
          const needsPort = PORT_REQUIRED.includes(p)
          const canBeTarget = !needsPort || (typeof listenPort === 'number' && listenPort > 0)
          let tagType: 'success' | 'warning' | 'default' = 'default'
          if (isSupported && canBeTarget) tagType = 'success'
          else if (isSupported && !canBeTarget) tagType = 'warning'
          const tag = h(NTag, { type: tagType, size: 'small' }, { default: () => p.toUpperCase() })
          let tooltip = ''
          if (!isSupported) tooltip = reasons[p] || '不支持'
          else if (!canBeTarget) tooltip = `${p.toUpperCase()} 探测可用，但此节点未开放 listen-port，不能作为内部 ${p.toUpperCase()} 目标`
          if (tooltip) {
            return h(NTooltip, null, {
              trigger: () => tag,
              default: () => tooltip,
            })
          }
          return tag
        }),
      })
    },
  },
  {
    title: '操作', key: 'actions', width: 280,
    render: (row) => {
      const buttons: any[] = [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: row.enabled ? 'warning' : 'success', onClick: () => handleToggle(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
        h(NButton, { size: 'small', type: 'info', onClick: () => handleDeploy(row.id) }, { default: () => '部署' }),
      ]
      buttons.push(h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
        trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
        default: () => '确定删除此节点？',
      }))
      return h(NSpace, { size: 4 }, { default: () => buttons })
    },
  },
]

onMounted(fetchNodes)
</script>

<template>
  <div>
    <NPageHeader title="节点管理">
      <template #extra>
        <NButton type="primary" @click="showCreate = true">添加节点</NButton>
      </template>
    </NPageHeader>

    <NDataTable
      :columns="columns"
      :data="nodes"
      :loading="loading"
      :pagination="{ page, pageSize: 20, itemCount: total, onChange: (p: number) => { page = p; fetchNodes() } }"
      :scroll-x="1720"
      style="margin-top: 16px"
    />

    <!-- Create Modal -->
    <NModal v-model:show="showCreate" preset="card" title="添加节点" style="width: 500px">
      <NForm>
        <NFormItem label="名称" required>
          <NInput v-model:value="createForm.name" placeholder="节点名称" />
        </NFormItem>
        <NFormItem label="标签 1"><NInput v-model:value="createForm.label_1" placeholder="可选" /></NFormItem>
        <NFormItem label="标签 2"><NInput v-model:value="createForm.label_2" placeholder="可选" /></NFormItem>
        <NFormItem label="标签 3"><NInput v-model:value="createForm.label_3" placeholder="可选" /></NFormItem>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleCreate">创建</NButton>
      </template>
    </NModal>

    <!-- Edit Modal -->
    <NModal v-model:show="showEdit" preset="card" title="编辑节点" style="width: 500px">
      <NForm>
        <NFormItem label="名称"><NInput v-model:value="editForm.name" /></NFormItem>
        <NFormItem label="标签 1"><NInput v-model:value="editForm.label_1" /></NFormItem>
        <NFormItem label="标签 2"><NInput v-model:value="editForm.label_2" /></NFormItem>
        <NFormItem label="标签 3"><NInput v-model:value="editForm.label_3" /></NFormItem>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleEdit">保存</NButton>
      </template>
    </NModal>

    <!-- Deploy Command Modal -->
    <NModal v-model:show="showDeploy" preset="card" title="Agent 部署" style="width: 680px">
      <p style="margin-bottom: 12px; color: #666;">
        在目标机器上执行以下命令即可完成 Agent 一键安装。
      </p>
      <p style="font-weight: bold; margin-bottom: 8px;">方式一：一键安装（推荐）</p>
      <NCode :code="deployScriptCommand" language="bash" word-wrap />
      <p style="font-weight: bold; margin: 16px 0 8px;">方式二：Docker 安装（NAT 模式，仅出站探测）</p>
      <NCode :code="deployDockerCommand" language="bash" word-wrap />
      <p style="font-weight: bold; margin: 16px 0 8px;">方式三：Docker 安装（开放端口，可作为 TCP/UDP 探测目标）</p>
      <NCode :code="deployDockerListenCommand" language="bash" word-wrap />
    </NModal>
  </div>
</template>

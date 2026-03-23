<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NModal, NForm, NFormItem, NInput, NTag,
  NPopconfirm, NCode, useMessage, NPageHeader
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
const showToken = ref(false)
const showDeploy = ref(false)
const showEdit = ref(false)
const newNodeToken = ref('')
const deployCommand = ref('')
const createForm = ref({ name: '', label_1: '', label_2: '', label_3: '' })
const editForm = ref<Partial<Node>>({})
const editingId = ref('')

async function fetchNodes() {
  loading.value = true
  try {
    const res = await getNodes({ page: page.value, per_page: 20 })
    nodes.value = res.data.items
    total.value = res.data.total
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
    newNodeToken.value = res.data.node.token || ''
    showCreate.value = false
    showToken.value = true
    createForm.value = { name: '', label_1: '', label_2: '', label_3: '' }
    fetchNodes()
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
    deployCommand.value = res.data.command
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
    render: (row) => h(NTag, { type: row.status === 'online' ? 'success' : 'error', size: 'small' }, { default: () => row.status === 'online' ? '在线' : '离线' }),
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
    title: '操作', key: 'actions', width: 280,
    render: (row) => h(NSpace, { size: 4 }, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: row.enabled ? 'warning' : 'success', onClick: () => handleToggle(row) }, { default: () => row.enabled ? '禁用' : '启用' }),
        h(NButton, { size: 'small', type: 'info', onClick: () => handleDeploy(row.id) }, { default: () => '部署' }),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除此节点？',
        }),
      ],
    }),
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

    <!-- Token Modal -->
    <NModal v-model:show="showToken" preset="card" title="节点 Token" style="width: 500px">
      <p style="color: #d03050; font-weight: bold;">
        ⚠️ 请妥善保存此 Token，它只会显示一次！
      </p>
      <NCode :code="newNodeToken" language="text" word-wrap />
    </NModal>

    <!-- Deploy Command Modal -->
    <NModal v-model:show="showDeploy" preset="card" title="部署命令" style="width: 600px">
      <NCode :code="deployCommand" language="bash" word-wrap />
    </NModal>
  </div>
</template>

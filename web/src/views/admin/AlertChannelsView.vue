<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NModal, NForm, NFormItem, NInput,
  NSwitch, NTag, NPopconfirm, useMessage, NPageHeader
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import {
  getAlertChannels, createAlertChannel, updateAlertChannel,
  deleteAlertChannel, testAlertChannel
} from '@/api/alerts'
import type { AlertChannel } from '@/types'

const message = useMessage()
const channels = ref<AlertChannel[]>([])
const loading = ref(false)

const showForm = ref(false)
const isEdit = ref(false)
const editingId = ref('')
const form = ref({ name: '', type: 'webhook', url: '', enabled: true })

async function fetchChannels() {
  loading.value = true
  try {
    const res = await getAlertChannels()
    channels.value = res.data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  form.value = { name: '', type: 'webhook', url: '', enabled: true }
  showForm.value = true
}

function openEdit(ch: AlertChannel) {
  isEdit.value = true
  editingId.value = ch.id
  form.value = { name: ch.name, type: ch.type, url: ch.url, enabled: ch.enabled }
  showForm.value = true
}

async function handleSubmit() {
  if (!form.value.name || !form.value.url) {
    message.warning('请填写必要字段')
    return
  }
  const data = {
    name: form.value.name,
    type: form.value.type,
    url: form.value.url,
    enabled: form.value.enabled,
  }
  try {
    if (isEdit.value) {
      await updateAlertChannel(editingId.value, data)
      message.success('更新成功')
    } else {
      await createAlertChannel(data)
      message.success('创建成功')
    }
    showForm.value = false
    fetchChannels()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '操作失败')
  }
}

async function handleDelete(id: string) {
  try {
    await deleteAlertChannel(id)
    message.success('删除成功')
    fetchChannels()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '删除失败')
  }
}

async function handleTest(id: string) {
  try {
    await testAlertChannel(id)
    message.success('测试消息已发送')
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '测试失败')
  }
}

const columns: DataTableColumns<AlertChannel> = [
  { title: 'ID', key: 'id', width: 220, ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', width: 160 },
  { title: '类型', key: 'type', width: 100 },
  { title: 'URL', key: 'url', width: 300, ellipsis: { tooltip: true } },
  {
    title: '启用', key: 'enabled', width: 70,
    render: (row) => h(NTag, { type: row.enabled ? 'success' : 'default', size: 'small' }, { default: () => row.enabled ? '是' : '否' }),
  },
  {
    title: '操作', key: 'actions', width: 220,
    render: (row) => h(NSpace, { size: 4 }, {
      default: () => [
        h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'info', onClick: () => handleTest(row.id) }, { default: () => '测试' }),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          trigger: () => h(NButton, { size: 'small', type: 'error' }, { default: () => '删除' }),
          default: () => '确定删除？',
        }),
      ],
    }),
  },
]

onMounted(fetchChannels)
</script>

<template>
  <div>
    <NPageHeader title="告警通道">
      <template #extra>
        <NButton type="primary" @click="openCreate">添加通道</NButton>
      </template>
    </NPageHeader>

    <NDataTable :columns="columns" :data="channels" :loading="loading" style="margin-top: 16px" />

    <NModal v-model:show="showForm" preset="card" :title="isEdit ? '编辑通道' : '添加通道'" style="width: 500px">
      <NForm label-placement="left" label-width="80">
        <NFormItem label="名称"><NInput v-model:value="form.name" /></NFormItem>
        <NFormItem label="Webhook URL"><NInput v-model:value="form.url" placeholder="https://..." /></NFormItem>
        <NFormItem label="启用"><NSwitch v-model:value="form.enabled" /></NFormItem>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleSubmit">{{ isEdit ? '保存' : '创建' }}</NButton>
      </template>
    </NModal>
  </div>
</template>

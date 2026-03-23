<script setup lang="ts">
import { onMounted, ref, h } from 'vue'
import {
  NDataTable, NButton, NSpace, NModal, NForm, NFormItem, NInput,
  NSelect, NTag, NPopconfirm, useMessage, NPageHeader
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { getUsers, createUser, updateUserRole, deleteUser } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'

const message = useMessage()
const authStore = useAuthStore()
const users = ref<User[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const showCreate = ref(false)
const showRole = ref(false)
const createForm = ref({ username: '', password: '', role: 'readonly' })
const roleForm = ref({ userId: '' as string, role: '' })

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '只读', value: 'readonly' },
]

const roleColor: Record<string, string> = {
  admin: 'error',
  readonly: 'info',
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await getUsers({ page: page.value, per_page: 20 })
    users.value = res.data.items
    total.value = res.data.pagination.total
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.username || !createForm.value.password) {
    message.warning('请填写用户名和密码')
    return
  }
  try {
    await createUser(createForm.value)
    showCreate.value = false
    createForm.value = { username: '', password: '', role: 'readonly' }
    message.success('创建成功')
    fetchUsers()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '创建失败')
  }
}

function openRoleEdit(user: User) {
  roleForm.value = { userId: user.id, role: user.role }
  showRole.value = true
}

async function handleRoleUpdate() {
  try {
    await updateUserRole(roleForm.value.userId, roleForm.value.role)
    showRole.value = false
    message.success('角色更新成功')
    fetchUsers()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '更新失败')
  }
}

async function handleDelete(id: string) {
  try {
    await deleteUser(id)
    message.success('删除成功')
    fetchUsers()
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '删除失败')
  }
}

const columns: DataTableColumns<User> = [
  { title: 'ID', key: 'id', width: 220, ellipsis: { tooltip: true } },
  { title: '用户名', key: 'username', width: 160 },
  {
    title: '角色', key: 'role', width: 100,
    render: (row) => h(NTag, { type: (roleColor[row.role] || 'default') as any, size: 'small' }, { default: () => row.role }),
  },
  { title: '创建者', key: 'created_by', width: 120, render: (row) => row.created_by || '-' },
  { title: '创建时间', key: 'created_at', width: 180 },
  {
    title: '操作', key: 'actions', width: 180,
    render: (row) => {
      const isSelf = row.id === authStore.user?.id
      return h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'small', disabled: isSelf, onClick: () => openRoleEdit(row) }, { default: () => '角色' }),
          h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
            trigger: () => h(NButton, { size: 'small', type: 'error', disabled: isSelf }, { default: () => '删除' }),
            default: () => '确定删除？',
          }),
        ],
      })
    },
  },
]

onMounted(fetchUsers)
</script>

<template>
  <div>
    <NPageHeader title="用户管理">
      <template #extra>
        <NButton type="primary" @click="showCreate = true">添加用户</NButton>
      </template>
    </NPageHeader>

    <NDataTable
      :columns="columns"
      :data="users"
      :loading="loading"
      :pagination="{ page, pageSize: 20, itemCount: total, onChange: (p: number) => { page = p; fetchUsers() } }"
      style="margin-top: 16px"
    />

    <NModal v-model:show="showCreate" preset="card" title="添加用户" style="width: 500px">
      <NForm label-placement="left" label-width="80">
        <NFormItem label="用户名"><NInput v-model:value="createForm.username" /></NFormItem>
        <NFormItem label="密码"><NInput v-model:value="createForm.password" type="password" /></NFormItem>
        <NFormItem label="角色"><NSelect v-model:value="createForm.role" :options="roleOptions" /></NFormItem>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleCreate">创建</NButton>
      </template>
    </NModal>

    <NModal v-model:show="showRole" preset="card" title="修改角色" style="width: 400px">
      <NForm label-placement="left" label-width="60">
        <NFormItem label="角色"><NSelect v-model:value="roleForm.role" :options="roleOptions" /></NFormItem>
      </NForm>
      <template #action>
        <NButton type="primary" @click="handleRoleUpdate">保存</NButton>
      </template>
    </NModal>
  </div>
</template>

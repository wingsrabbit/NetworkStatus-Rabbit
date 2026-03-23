<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, NSpace, useMessage } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const message = useMessage()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    message.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await authStore.login(form.value.username, form.value.password)
    message.success('登录成功')
    router.push('/')
  } catch (err: any) {
    const msg = err.response?.data?.error?.message || '登录失败'
    message.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <NCard title="NetworkStatus-Rabbit" style="width: 400px">
      <NForm @submit.prevent="handleLogin">
        <NFormItem label="用户名">
          <NInput v-model:value="form.username" placeholder="请输入用户名" />
        </NFormItem>
        <NFormItem label="密码">
          <NInput v-model:value="form.password" type="password" placeholder="请输入密码" show-password-on="click" @keydown.enter="handleLogin" />
        </NFormItem>
        <NSpace justify="end">
          <NButton type="primary" :loading="loading" @click="handleLogin">登录</NButton>
        </NSpace>
      </NForm>
    </NCard>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}
</style>

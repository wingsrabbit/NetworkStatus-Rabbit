<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NCard, NForm, NFormItem, NInputNumber, NButton, NSpace, useMessage, NPageHeader
} from 'naive-ui'
import { getSettings, updateSettings } from '@/api/settings'

const message = useMessage()
const loading = ref(false)
const form = ref<Record<string, any>>({
  heartbeat_window: 120,
  offline_threshold: 20,
  heartbeat_check_interval: 10,
  snapshot_push_interval: 1,
  default_probe_timeout: 10,
  default_probe_interval: 5,
})

async function fetchSettings() {
  try {
    const res = await getSettings()
    form.value = { ...form.value, ...res.data.settings }
  } catch (err: any) {
    message.error('获取设置失败')
  }
}

async function handleSave() {
  loading.value = true
  try {
    await updateSettings(form.value)
    message.success('保存成功')
  } catch (err: any) {
    message.error(err.response?.data?.error?.message || '保存失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchSettings)
</script>

<template>
  <div>
    <NPageHeader title="系统设置" />
    <NCard style="margin-top: 16px; max-width: 600px">
      <NForm label-placement="left" label-width="160">
        <NFormItem label="心跳窗口 (秒)">
          <NInputNumber v-model:value="form.heartbeat_window" :min="30" :max="600" style="width: 100%" />
        </NFormItem>
        <NFormItem label="离线阈值 (次)">
          <NInputNumber v-model:value="form.offline_threshold" :min="1" :max="100" style="width: 100%" />
        </NFormItem>
        <NFormItem label="心跳检测间隔 (秒)">
          <NInputNumber v-model:value="form.heartbeat_check_interval" :min="1" :max="60" style="width: 100%" />
        </NFormItem>
        <NFormItem label="快照推送间隔 (秒)">
          <NInputNumber v-model:value="form.snapshot_push_interval" :min="1" :max="10" style="width: 100%" />
        </NFormItem>
        <NFormItem label="默认探测超时 (秒)">
          <NInputNumber v-model:value="form.default_probe_timeout" :min="1" :max="30" style="width: 100%" />
        </NFormItem>
        <NFormItem label="默认探测间隔 (秒)">
          <NInputNumber v-model:value="form.default_probe_interval" :min="1" :max="60" style="width: 100%" />
        </NFormItem>
        <NFormItem>
          <NSpace>
            <NButton type="primary" :loading="loading" @click="handleSave">保存设置</NButton>
          </NSpace>
        </NFormItem>
      </NForm>
    </NCard>
  </div>
</template>

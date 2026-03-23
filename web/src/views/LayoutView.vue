<script setup lang="ts">
import { h, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent,
  NMenu, NButton, NSpace, NIcon, NSwitch, NAvatar, NDropdown, NText
} from 'naive-ui'
import {
  HomeOutline, ServerOutline, ListOutline, NotificationsOutline,
  TimeOutline, PeopleOutline, SettingsOutline, SunnyOutline, MoonOutline,
  LogOutOutline
} from '@vicons/ionicons5'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useSocket } from '@/composables/useSocket'
import { onMounted, onUnmounted } from 'vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const { connect, disconnect } = useSocket()

onMounted(() => connect())
onUnmounted(() => disconnect())

function renderIcon(icon: any) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions = computed(() => {
  const items: any[] = [
    { label: '仪表盘', key: '/', icon: renderIcon(HomeOutline) },
  ]
  if (authStore.isOperator) {
    items.push(
      { label: '节点管理', key: '/nodes', icon: renderIcon(ServerOutline) },
      { label: '任务管理', key: '/tasks', icon: renderIcon(ListOutline) },
      { label: '告警通道', key: '/alerts/channels', icon: renderIcon(NotificationsOutline) },
    )
  }
  items.push(
    { label: '告警历史', key: '/alerts/history', icon: renderIcon(TimeOutline) },
  )
  if (authStore.isAdmin) {
    items.push(
      { label: '用户管理', key: '/users', icon: renderIcon(PeopleOutline) },
      { label: '系统设置', key: '/settings', icon: renderIcon(SettingsOutline) },
    )
  }
  return items
})

const activeKey = computed(() => {
  return route.path
})

function handleMenuUpdate(key: string) {
  router.push(key)
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

const userDropdownOptions = [
  { label: '退出登录', key: 'logout', icon: renderIcon(LogOutOutline) },
]

function handleUserAction(key: string) {
  if (key === 'logout') handleLogout()
}
</script>

<template>
  <NLayout has-sider style="height: 100vh">
    <NLayoutSider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      show-trigger
      content-style="padding: 8px 0;"
    >
      <div style="padding: 16px; text-align: center; font-weight: bold; font-size: 16px;">
        🐇 NSR
      </div>
      <NMenu
        :options="menuOptions"
        :value="activeKey"
        @update:value="handleMenuUpdate"
      />
    </NLayoutSider>
    <NLayout>
      <NLayoutHeader bordered style="height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: flex-end;">
        <NSpace align="center" :size="16">
          <NButton quaternary circle @click="themeStore.toggle">
            <template #icon>
              <NIcon>
                <MoonOutline v-if="!themeStore.isDark" />
                <SunnyOutline v-else />
              </NIcon>
            </template>
          </NButton>
          <NDropdown :options="userDropdownOptions" @select="handleUserAction">
            <NButton quaternary>
              {{ authStore.user?.username }} ({{ authStore.user?.role }})
            </NButton>
          </NDropdown>
        </NSpace>
      </NLayoutHeader>
      <NLayoutContent content-style="padding: 24px;" :native-scrollbar="false">
        <router-view />
      </NLayoutContent>
    </NLayout>
  </NLayout>
</template>

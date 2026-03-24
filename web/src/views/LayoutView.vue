<script setup lang="ts">
import { h, computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent, NLayoutFooter,
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
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

declare const __APP_VERSION__: string
const appVersion = __APP_VERSION__

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const { connect, disconnect } = useSocket()

// Footer status bar
const currentTime = ref(dayjs().tz('Asia/Shanghai').format('YY/MM/DD HH:mm:ss'))
const lastUpdateLabel = ref('等待数据')
let _lastDataTime = 0
let _footerTimer: ReturnType<typeof setInterval> | null = null

function tickFooter() {
  currentTime.value = dayjs().tz('Asia/Shanghai').format('YY/MM/DD HH:mm:ss')
  if (_lastDataTime > 0) {
    const sec = Math.floor((Date.now() - _lastDataTime) / 1000)
    lastUpdateLabel.value = sec < 10 ? '10秒内' : `${sec}秒前`
  }
}

/** Called from anywhere to mark "we just received fresh data". */
function markDataReceived() {
  _lastDataTime = Date.now()
  lastUpdateLabel.value = '10秒内'
}

// Expose globally so child views can call it
;(window as any).__nsr_markDataReceived = markDataReceived

onMounted(() => {
  connect()
  _footerTimer = setInterval(tickFooter, 1000)
})
onUnmounted(() => {
  disconnect()
  if (_footerTimer) clearInterval(_footerTimer)
})

function renderIcon(icon: any) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions = computed(() => {
  const items: any[] = [
    { label: '仪表盘', key: '/dashboard', icon: renderIcon(HomeOutline) },
  ]
  if (authStore.isAdmin) {
    items.push(
      { label: '节点管理', key: '/admin/nodes', icon: renderIcon(ServerOutline) },
      { label: '任务管理', key: '/admin/tasks', icon: renderIcon(ListOutline) },
      { label: '告警通道', key: '/admin/alerts', icon: renderIcon(NotificationsOutline) },
    )
  }
  items.push(
    { label: '告警历史', key: '/admin/alerts/history', icon: renderIcon(TimeOutline) },
  )
  if (authStore.isAdmin) {
    items.push(
      { label: '用户管理', key: '/admin/users', icon: renderIcon(PeopleOutline) },
      { label: '系统设置', key: '/admin/settings', icon: renderIcon(SettingsOutline) },
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
        <span style="font-size: 11px; font-weight: normal; opacity: 0.5; margin-left: 4px;">v{{ appVersion }}</span>
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
      <NLayoutFooter bordered style="height: 36px; display: flex; align-items: center; justify-content: center; font-size: 12px; opacity: 0.6;">
        Powered by NetworkStatus-Rabbit · 现在时间（GMT+8）：{{ currentTime }} · 最后更新：{{ lastUpdateLabel }}
      </NLayoutFooter>
    </NLayout>
  </NLayout>
</template>

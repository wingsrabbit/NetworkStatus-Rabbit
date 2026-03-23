import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { getMe, login as apiLogin, logout as apiLogout } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isOperator = computed(() => user.value?.role === 'operator' || user.value?.role === 'admin')

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await apiLogin(username, password)
      user.value = res.data.user
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    await apiLogout()
    user.value = null
  }

  async function fetchUser() {
    try {
      const res = await getMe()
      user.value = res.data.user
    } catch {
      user.value = null
    }
  }

  return { user, loading, isAuthenticated, isAdmin, isOperator, login, logout, fetchUser }
})

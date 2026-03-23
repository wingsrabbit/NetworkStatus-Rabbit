import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { darkTheme } from 'naive-ui'
import type { GlobalTheme } from 'naive-ui'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(localStorage.getItem('theme') === 'dark')
  const theme = ref<GlobalTheme | null>(isDark.value ? darkTheme : null)

  function toggle() {
    isDark.value = !isDark.value
    theme.value = isDark.value ? darkTheme : null
    localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
    updateBodyClass()
  }

  function updateBodyClass() {
    if (isDark.value) {
      document.body.classList.add('dark')
    } else {
      document.body.classList.remove('dark')
    }
  }

  // Init
  updateBodyClass()

  return { isDark, theme, toggle }
})

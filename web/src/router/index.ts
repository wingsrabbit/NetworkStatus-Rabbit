import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/LayoutView.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
      },
      {
        path: 'dashboard/:taskId',
        name: 'TaskDetail',
        component: () => import('@/views/TaskDetailView.vue'),
        props: true,
      },
      {
        path: 'admin/nodes',
        name: 'Nodes',
        component: () => import('@/views/admin/NodesView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'admin/tasks',
        name: 'Tasks',
        component: () => import('@/views/admin/TasksView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'admin/alerts',
        name: 'AlertChannels',
        component: () => import('@/views/admin/AlertChannelsView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'admin/alerts/history',
        name: 'AlertHistory',
        component: () => import('@/views/admin/AlertHistoryView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'admin/users',
        name: 'Users',
        component: () => import('@/views/admin/UsersView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'admin/settings',
        name: 'Settings',
        component: () => import('@/views/admin/SettingsView.vue'),
        meta: { requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  if (!authStore.user && to.meta.requiresAuth !== false) {
    await authStore.fetchUser()
  }

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    return next('/login')
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return next('/dashboard')
  }

  if (to.path === '/login' && authStore.isAuthenticated) {
    return next('/dashboard')
  }

  next()
})

export default router

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
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
      },
      {
        path: 'task/:id',
        name: 'TaskDetail',
        component: () => import('@/views/TaskDetailView.vue'),
        props: true,
      },
      {
        path: 'nodes',
        name: 'Nodes',
        component: () => import('@/views/admin/NodesView.vue'),
        meta: { requiresOperator: true },
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/admin/TasksView.vue'),
        meta: { requiresOperator: true },
      },
      {
        path: 'alerts/channels',
        name: 'AlertChannels',
        component: () => import('@/views/admin/AlertChannelsView.vue'),
        meta: { requiresOperator: true },
      },
      {
        path: 'alerts/history',
        name: 'AlertHistory',
        component: () => import('@/views/admin/AlertHistoryView.vue'),
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/admin/UsersView.vue'),
        meta: { requiresAdmin: true },
      },
      {
        path: 'settings',
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

  if (!authStore.user) {
    await authStore.fetchUser()
  }

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    return next('/login')
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return next('/')
  }

  if (to.meta.requiresOperator && !authStore.isOperator) {
    return next('/')
  }

  if (to.path === '/login' && authStore.isAuthenticated) {
    return next('/')
  }

  next()
})

export default router

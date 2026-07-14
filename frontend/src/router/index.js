import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('../views/Chat.vue'),
    meta: { title: '对话' },
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('../views/KnowledgeBase.vue'),
    meta: { title: '知识库' },
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('../views/ContentWorkbench.vue'),
    meta: { title: '内容工作台' },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/Admin.vue'),
    meta: { title: '管理', admin: true },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.meta.public) return next()
  const token = localStorage.getItem('token')
  if (!token) return next({ path: '/login', query: { redirect: to.fullPath } })
  if (to.meta.admin) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      if (user.role !== 'admin') return next('/chat')
    } catch {
      return next('/login')
    }
  }
  next()
})

export default router

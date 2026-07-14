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
    meta: { title: '智能对话' },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '数据看板' },
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('../views/ContentWorkbench.vue'),
    meta: { title: '内容工作台' },
  },
  {
    path: '/multi-agent',
    name: 'MultiAgent',
    component: () => import('../views/MultiAgent.vue'),
    meta: { title: '多智能体协调' },
  },
  {
    path: '/help',
    name: 'HelpCenter',
    component: () => import('../views/HelpCenter.vue'),
    meta: { title: '帮助中心' },
  },
  {
    path: '/security',
    name: 'Security',
    component: () => import('../views/Security.vue'),
    meta: { title: '安全管理', userOnly: true },
  },
  // —— 以下仅管理员 ——
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('../views/KnowledgeBase.vue'),
    meta: { title: '知识库管理', admin: true },
  },
  {
    path: '/rag',
    name: 'RagSettings',
    component: () => import('../views/RagSettings.vue'),
    meta: { title: 'RAG 参数', admin: true },
  },
  {
    path: '/kb-status',
    name: 'KbStatus',
    component: () => import('../views/KbStatus.vue'),
    meta: { title: '知识库状态', admin: true },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/Admin.vue'),
    meta: { title: '系统管理', admin: true },
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
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (to.meta.admin && user.role !== 'admin') return next('/chat')
    // 安全管理页仅普通用户；管理员在系统管理里改密
    if (to.meta.userOnly && user.role === 'admin') return next('/admin')
  } catch {
    return next('/login')
  }
  next()
})

export default router

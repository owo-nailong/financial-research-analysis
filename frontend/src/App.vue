<template>
  <div v-if="isLoginPage" class="full">
    <router-view />
  </div>

  <div v-else class="shell">
    <aside class="sidebar" :class="{ collapsed }">
      <!-- 品牌 + 模型 -->
      <div class="brand" @click="goChat">
        <div class="logo" aria-hidden="true">
          <svg viewBox="0 0 40 40" width="32" height="32">
            <rect width="40" height="40" rx="10" fill="#111" />
            <path d="M10 26 L16 12 L22 22 L26 16 L30 26 Z" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" />
            <circle cx="28" cy="12" r="2.2" fill="#fff" />
          </svg>
        </div>
        <div v-if="!collapsed" class="brand-text">
          <div class="brand-name">智研AI</div>
          <div class="brand-model" :title="modelName">{{ modelName }}</div>
        </div>
      </div>

      <div class="side-top">
        <button class="new-chat" type="button" @click="goChat">
          <span class="icon-plus">+</span>
          <span v-if="!collapsed">新建对话</span>
        </button>
      </div>

      <nav class="nav">
        <div v-if="!collapsed" class="nav-section-label">使用</div>
        <div v-else class="nav-divider" />
        <router-link
          v-for="item in userNav"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          :title="item.label"
        >
          <span v-if="collapsed" class="nav-short">{{ item.short }}</span>
          <span v-else class="nav-label">{{ item.label }}</span>
        </router-link>

        <template v-if="isAdmin">
          <div v-if="!collapsed" class="nav-section-label admin-section">管理</div>
          <div v-else class="nav-divider strong" />
          <router-link
            v-for="item in adminNav"
            :key="item.path"
            :to="item.path"
            class="nav-item admin-item"
            :class="{ active: isActive(item.path) }"
            :title="item.label + '（仅管理员）'"
          >
            <span v-if="collapsed" class="nav-short">{{ item.short }}</span>
            <span v-else class="nav-label">{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <div class="side-spacer" />

      <div class="side-bottom">
        <button class="collapse-btn" type="button" @click="collapsed = !collapsed">
          {{ collapsed ? '>' : '收起侧栏' }}
        </button>
        <div v-if="!collapsed" class="user-box">
          <div class="user-name">{{ user.display_name || user.username || '用户' }}</div>
          <div class="user-account">{{ user.username || '' }}</div>
          <button class="logout" type="button" @click="logout">退出登录</button>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar-title">{{ route.meta?.title || '智研AI' }}</div>
        <div class="topbar-right">
          <span class="sys">
            <i class="dot" :class="systemOk ? 'ok' : 'bad'" />
            {{ systemLabel }}
          </span>
        </div>
      </header>
      <div class="content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { healthCheck } from './api'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const isLoginPage = computed(() => route.path === '/login')
const isAdmin = computed(() => user.value?.role === 'admin')

/** 使用区导航；普通用户额外提供「安全管理」改密入口 */
const userNav = computed(() => {
  const base = [
    { path: '/chat', label: '智能对话', short: '对话' },
    { path: '/dashboard', label: '数据看板', short: '看板' },
    { path: '/workbench', label: '内容工作台', short: '工作台' },
    { path: '/multi-agent', label: '多智能体', short: '协同' },
    { path: '/help', label: '帮助中心', short: '帮助' },
  ]
  if (!isAdmin.value) {
    base.push({ path: '/security', label: '安全管理', short: '安全' })
  }
  return base
})

/** 仅管理员：知识库与系统配置（含改全部用户密码） */
const adminNav = [
  { path: '/knowledge', label: '知识库管理', short: '库' },
  { path: '/rag', label: 'RAG 参数', short: 'RAG' },
  { path: '/kb-status', label: '知识库状态', short: '状态' },
  { path: '/admin', label: '系统管理', short: '管理' },
]

const systemOk = ref(false)
const systemLabel = ref('检测中')
const modelName = ref('加载中...')

function isActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}

function goChat() {
  router.push('/chat')
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

async function refreshHealth() {
  try {
    const health = await healthCheck()
    systemOk.value = health.status === 'ok'
    const db = health.database?.backend || '?'
    const redis = health.redis?.ok ? 'Redis' : 'NoRedis'
    const llm = health.ollama?.ok ? 'Ollama' : 'NoLLM'
    systemLabel.value = `${db} / ${redis} / ${llm}`
    modelName.value = health.llm?.model || health.ollama?.models?.[0] || '本地模型'
  } catch {
    systemOk.value = false
    systemLabel.value = '后端未连接'
    modelName.value = '模型未连接'
  }
}

onMounted(async () => {
  if (!isLoginPage.value) {
    user.value = JSON.parse(localStorage.getItem('user') || '{}')
    await refreshHealth()
  }
})

watch(
  () => route.path,
  async () => {
    if (!isLoginPage.value) {
      user.value = JSON.parse(localStorage.getItem('user') || '{}')
      await refreshHealth()
    }
  }
)
</script>

<style scoped>
.full {
  height: 100%;
}

.shell {
  display: flex;
  height: 100vh;
  background: var(--bg);
}

.sidebar {
  width: 248px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 72px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}

.sidebar.collapsed .brand {
  justify-content: center;
  padding: 14px 8px 8px;
}

.logo {
  flex-shrink: 0;
  line-height: 0;
}

.brand-text {
  min-width: 0;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.25;
}

.brand-model {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

.side-top {
  padding: 10px 12px 6px;
}

.new-chat {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  cursor: pointer;
  color: var(--text);
  font-size: 14px;
}

.sidebar:not(.collapsed) .new-chat {
  justify-content: flex-start;
}

.new-chat:hover {
  background: var(--bg-hover);
}

.icon-plus {
  font-size: 18px;
  line-height: 1;
  font-weight: 400;
}

.nav {
  padding: 4px 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-section-label {
  margin: 10px 8px 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.nav-section-label.admin-section {
  margin-top: 14px;
  color: #666;
}

.nav-divider {
  height: 1px;
  background: var(--border);
  margin: 8px 6px;
}

.nav-divider.strong {
  margin-top: 12px;
  background: #d0d0d0;
}

.nav-item {
  padding: 11px 12px;
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 14.5px;
  display: block;
  text-align: left;
  line-height: 1.35;
}

.sidebar.collapsed .nav-item {
  text-align: center;
  padding: 10px 6px;
  font-size: 12px;
}

.nav-item:hover {
  background: var(--bg-hover);
}

.nav-item.active {
  background: var(--bg-active);
  font-weight: 600;
}

.nav-item.admin-item {
  color: #333;
}

.side-spacer {
  flex: 1;
}

.side-bottom {
  border-top: 1px solid var(--border);
  padding: 14px 14px 16px;
}

.collapse-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 12px;
  width: 100%;
  text-align: left;
}

.sidebar.collapsed .collapse-btn {
  text-align: center;
}

.user-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 2px 0;
}

.user-name {
  font-size: 15px;
  font-weight: 650;
  line-height: 1.35;
  color: var(--text);
  letter-spacing: -0.01em;
}

.user-account {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.3;
}

.logout {
  margin-top: 6px;
  align-self: flex-start;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}

.logout:hover {
  background: var(--bg-hover);
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg);
}

.topbar {
  height: 52px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.topbar-title {
  font-size: 17px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.sys {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>

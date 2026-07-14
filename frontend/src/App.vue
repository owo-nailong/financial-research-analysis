<template>
  <div v-if="isLoginPage" class="full">
    <router-view />
  </div>

  <div v-else class="shell">
    <aside class="sidebar" :class="{ collapsed }">
      <div class="side-top">
        <button class="new-chat" type="button" @click="goChat">
          <span class="icon-plus">+</span>
          <span v-if="!collapsed">新建对话</span>
        </button>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path.startsWith(item.path) }"
        >
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div v-if="!collapsed" class="side-panel">
        <div class="panel-title">RAG 参数</div>
        <div class="panel-body">
          <label class="field">
            <span>启用 RAG</span>
            <input type="checkbox" v-model="ragForm.enabled" :disabled="!isAdmin" @change="saveRag" />
          </label>
          <label class="field">
            <span>Top K</span>
            <input type="number" min="1" max="20" v-model.number="ragForm.top_k" :disabled="!isAdmin" @change="saveRag" />
          </label>
          <label class="field">
            <span>Chunk</span>
            <input type="number" min="100" max="4000" step="50" v-model.number="ragForm.chunk_size" :disabled="!isAdmin" @change="saveRag" />
          </label>
          <label class="field">
            <span>Overlap</span>
            <input type="number" min="0" max="1000" step="10" v-model.number="ragForm.chunk_overlap" :disabled="!isAdmin" @change="saveRag" />
          </label>
          <label class="field">
            <span>阈值</span>
            <input type="number" min="0" max="1" step="0.05" v-model.number="ragForm.score_threshold" :disabled="!isAdmin" @change="saveRag" />
          </label>
          <p v-if="!isAdmin" class="hint">仅管理员可修改</p>
        </div>

        <div class="panel-title">知识库状态</div>
        <div class="panel-body status-box">
          <div class="status-row">
            <span>向量索引</span>
            <span>
              <i class="dot" :class="kbUsable ? 'ok' : 'bad'" />
              {{ kbUsable ? '可用' : '不可用' }}
            </span>
          </div>
          <div class="status-row">
            <span>文档数</span>
            <span>{{ kbMeta.document_count ?? '-' }}</span>
          </div>
          <div class="status-row">
            <span>分块数</span>
            <span>{{ kbMeta.chunk_count ?? '-' }}</span>
          </div>
          <div class="status-row">
            <span>嵌入服务</span>
            <span>
              <i class="dot" :class="embedOk ? 'ok' : 'bad'" />
              {{ embedOk ? '在线' : '离线' }}
            </span>
          </div>
          <div v-if="sources.length" class="sources">
            <div class="sources-title">来源</div>
            <div v-for="s in sources.slice(0, 6)" :key="s.doc_id" class="source-item">
              <div class="source-name" :title="s.title">{{ s.title }}</div>
              <div class="source-url" :title="s.source_url || s.file_path">
                <i class="dot" :class="s.reachable ? 'ok' : 'warn'" />
                {{ shortSource(s) }}
              </div>
            </div>
          </div>
          <button class="linkish" type="button" @click="refreshStatus">刷新状态</button>
        </div>
      </div>

      <div class="side-bottom">
        <button class="collapse-btn" type="button" @click="collapsed = !collapsed">
          {{ collapsed ? '>' : '收起' }}
        </button>
        <div v-if="!collapsed" class="user-box">
          <div class="user-name">{{ user.display_name || user.username || '用户' }}</div>
          <div class="user-role">{{ user.role === 'admin' ? '管理员' : '使用者' }}</div>
          <button class="logout" type="button" @click="logout">退出</button>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getRagParams, updateRagParams, kbStatus, healthCheck } from './api'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const user = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const isLoginPage = computed(() => route.path === '/login')
const isAdmin = computed(() => user.value?.role === 'admin')

const navItems = computed(() => {
  const items = [
    { path: '/chat', label: '智能对话' },
    { path: '/knowledge', label: '知识库' },
    { path: '/workbench', label: '内容工作台' },
  ]
  if (isAdmin.value) items.push({ path: '/admin', label: '系统管理' })
  return items
})

const ragForm = reactive({
  enabled: true,
  top_k: 5,
  chunk_size: 800,
  chunk_overlap: 120,
  score_threshold: 0.15,
})
const kbMeta = ref({})
const sources = ref([])
const embedOk = ref(false)
const kbUsable = ref(false)
const systemOk = ref(false)
const systemLabel = ref('检测中')

function shortSource(s) {
  const u = s.source_url || s.file_path || '无来源'
  return u.length > 36 ? u.slice(0, 34) + '...' : u
}

function goChat() {
  router.push('/chat')
}

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

async function loadRag() {
  try {
    const res = await getRagParams()
    Object.assign(ragForm, res.params || {})
    kbMeta.value = res.store || {}
  } catch {
    /* ignore when not logged in */
  }
}

async function saveRag() {
  if (!isAdmin.value) return
  try {
    const res = await updateRagParams({ ...ragForm })
    Object.assign(ragForm, res.params || {})
  } catch (e) {
    console.error(e)
  }
}

async function refreshStatus() {
  try {
    const [st, health] = await Promise.all([kbStatus(), healthCheck()])
    sources.value = st.sources || []
    kbMeta.value = st.vector_store || {}
    embedOk.value = !!st.embedding?.reachable
    kbUsable.value = !!st.vector_store?.usable
    systemOk.value = health.status === 'ok'
    const db = health.database?.backend || '?'
    const redis = health.redis?.ok ? 'Redis' : 'NoRedis'
    const llm = health.ollama?.ok ? 'Ollama' : 'NoLLM'
    systemLabel.value = `${db} / ${redis} / ${llm}`
  } catch {
    systemOk.value = false
    systemLabel.value = '后端未连接'
  }
}

onMounted(async () => {
  if (!isLoginPage.value) {
    user.value = JSON.parse(localStorage.getItem('user') || '{}')
    await loadRag()
    await refreshStatus()
  }
})

watch(
  () => route.path,
  async () => {
    if (!isLoginPage.value) {
      user.value = JSON.parse(localStorage.getItem('user') || '{}')
      await refreshStatus()
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
  width: 260px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: 64px;
}

.side-top {
  padding: 12px;
}

.new-chat {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: #fff;
  cursor: pointer;
  color: var(--text);
  font-size: 14px;
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

.nav-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: 14px;
}

.nav-item:hover {
  background: var(--bg-hover);
}

.nav-item.active {
  background: var(--bg-active);
  font-weight: 600;
}

.side-panel {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 12px;
  border-top: 1px solid var(--border);
}

.panel-title {
  margin-top: 14px;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: none;
  letter-spacing: 0.02em;
}

.panel-body {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

.field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.field input[type='number'] {
  width: 72px;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 12px;
  background: #fff;
}

.field input[type='checkbox'] {
  width: 14px;
  height: 14px;
}

.hint {
  font-size: 11px;
  color: var(--text-muted);
}

.status-box {
  font-size: 12px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  color: var(--text-secondary);
}

.sources {
  margin-top: 8px;
  border-top: 1px solid var(--border);
  padding-top: 8px;
}

.sources-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text);
}

.source-item {
  margin-bottom: 8px;
}

.source-name {
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-url {
  color: var(--text-muted);
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.linkish {
  margin-top: 8px;
  border: none;
  background: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
  padding: 0;
}

.side-bottom {
  border-top: 1px solid var(--border);
  padding: 10px 12px 14px;
}

.collapse-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  margin-bottom: 8px;
}

.user-box {
  font-size: 12px;
}

.user-name {
  font-weight: 600;
}

.user-role {
  color: var(--text-muted);
  margin: 2px 0 8px;
}

.logout {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
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
  font-size: 15px;
  font-weight: 600;
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

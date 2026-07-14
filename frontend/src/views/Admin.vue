<template>
  <div class="admin-page">
    <header class="page-head">
      <div>
        <h1>系统管理</h1>
        <p class="lead">运行状态监控、用户权限与账号安全配置。</p>
      </div>
      <button type="button" class="btn" :disabled="loading" @click="refreshAll">
        {{ loading ? '刷新中...' : '刷新状态' }}
      </button>
    </header>

    <!-- Status tiles -->
    <section class="status-grid">
      <div class="stat" :class="health.database?.ok ? 'ok' : 'bad'">
        <span class="stat-label">数据库</span>
        <strong class="stat-value">{{ health.database?.ok ? '正常' : '异常' }}</strong>
        <span class="stat-meta">{{ health.database?.backend || '—' }} · {{ health.database?.database || '' }}</span>
      </div>
      <div class="stat" :class="health.redis?.ok ? 'ok' : 'bad'">
        <span class="stat-label">Redis</span>
        <strong class="stat-value">{{ health.redis?.ok ? '正常' : '异常' }}</strong>
        <span class="stat-meta">{{ health.redis?.host || '—' }}{{ health.redis?.port ? ':' + health.redis.port : '' }}</span>
      </div>
      <div class="stat" :class="health.ollama?.ok ? 'ok' : 'bad'">
        <span class="stat-label">Ollama</span>
        <strong class="stat-value">{{ health.ollama?.ok ? '在线' : '离线' }}</strong>
        <span class="stat-meta">{{ health.llm?.model || health.ollama?.models?.[0] || '未配置模型' }}</span>
      </div>
      <div class="stat" :class="(health.rag?.chunks || 0) > 0 ? 'ok' : 'warn'">
        <span class="stat-label">知识库向量</span>
        <strong class="stat-value">{{ health.rag?.docs ?? '—' }} 篇</strong>
        <span class="stat-meta">{{ health.rag?.chunks ?? 0 }} 分块 · RAG {{ health.rag?.enabled === false ? '关闭' : '开启' }}</span>
      </div>
    </section>

    <div class="layout">
      <!-- Users -->
      <section class="panel users-panel">
        <div class="panel-head">
          <div>
            <h2>用户管理</h2>
            <p class="panel-desc">管理系统账号：创建用户、调整角色、重置密码。</p>
          </div>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>用户名</th>
                <th>角色</th>
                <th>显示名</th>
                <th class="col-action">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.username">
                <td class="mono">{{ u.username }}</td>
                <td>
                  <span class="role" :class="u.role">{{ roleLabel(u.role) }}</span>
                </td>
                <td>{{ u.display_name || '—' }}</td>
                <td class="col-action">
                  <button type="button" class="btn sm" @click="openReset(u)">修改密码</button>
                </td>
              </tr>
              <tr v-if="!users.length">
                <td colspan="4" class="empty">暂无用户</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="create-box">
          <h3>创建用户</h3>
          <div class="create-form">
            <input v-model="form.username" placeholder="用户名" autocomplete="off" />
            <input
              v-model="form.password"
              type="password"
              placeholder="密码（至少 6 位）"
              autocomplete="new-password"
            />
            <select v-model="form.role">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
            <button type="button" class="btn primary" @click="addUser">创建</button>
          </div>
        </div>

        <p v-if="msg" class="toast" :class="{ err: msgIsError }">{{ msg }}</p>
      </section>

      <!-- Side column: service + tools -->
      <aside class="side-col">
        <section class="panel">
          <h2>服务信息</h2>
          <dl class="kv">
            <div>
              <dt>服务名</dt>
              <dd>{{ health.service || '智研AI' }}</dd>
            </div>
            <div>
              <dt>版本</dt>
              <dd>{{ health.version || '—' }}</dd>
            </div>
            <div>
              <dt>LLM</dt>
              <dd>{{ health.llm?.provider || '—' }} / {{ health.llm?.model || '—' }}</dd>
            </div>
            <div>
              <dt>工具数</dt>
              <dd>{{ health.tools_count ?? '—' }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>
                <span class="dot" :class="health.status === 'ok' ? 'ok' : 'bad'" />
                {{ health.status || '未知' }}
              </dd>
            </div>
          </dl>
        </section>

        <section class="panel">
          <h2>数据维护</h2>
          <p class="panel-desc">
            对知识库资料与演示数据执行维护操作。业务文件默认存放于系统数据目录。
          </p>
          <div class="actions-stack">
            <button type="button" class="btn block" :disabled="working" @click="ingestDocs">
              {{ working ? '处理中...' : '导入数据目录至知识库' }}
            </button>
            <button type="button" class="btn block" :disabled="working" @click="reseed">
              {{ working ? '处理中...' : '重建演示数据集' }}
            </button>
          </div>
          <p class="hint">
            「导入数据目录」将扫描 data 下可识别的文档（文本 / Markdown / CSV / PDF 等），
            自动跳过向量索引、数据库等运行时文件，并写入知识库供 RAG 检索。
          </p>
        </section>
      </aside>
    </div>

    <div v-if="resetUser" class="modal" @click.self="resetUser = null">
      <div class="modal-card">
        <h3>修改密码</h3>
        <p class="modal-sub">账号：<strong>{{ resetUser.username }}</strong></p>
        <label>
          新密码
          <input
            v-model="resetPwd"
            type="password"
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </label>
        <div class="modal-actions">
          <button type="button" class="btn" @click="resetUser = null">取消</button>
          <button type="button" class="btn primary" :disabled="saving" @click="doReset">
            {{ saving ? '提交中...' : '确认修改' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  adminSetPassword,
  createUser,
  getAuthPublicKey,
  healthCheck,
  ingestReferences,
  listUsers,
} from '../api'
import { encryptPassword, loadPublicKey } from '../utils/crypto'
import axios from 'axios'

const health = ref({})
const users = ref([])
const msg = ref('')
const msgIsError = ref(false)
const loading = ref(false)
const saving = ref(false)
const working = ref(false)
const form = ref({ username: '', password: '', role: 'user' })
const resetUser = ref(null)
const resetPwd = ref('')

function roleLabel(role) {
  return role === 'admin' ? '管理员' : '普通用户'
}

function setMsg(text, isError = false) {
  msg.value = text
  msgIsError.value = isError
}

async function ensureKey() {
  await loadPublicKey(getAuthPublicKey)
}

async function loadHealth() {
  try {
    health.value = await healthCheck()
  } catch (e) {
    health.value = { status: 'error', service: e.message }
  }
}

async function loadUsers() {
  try {
    const res = await listUsers()
    users.value = res.data || []
  } catch (e) {
    setMsg(e.message, true)
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadHealth(), loadUsers()])
  } finally {
    loading.value = false
  }
}

async function addUser() {
  setMsg('')
  try {
    if (!form.value.username || !form.value.password) {
      setMsg('请填写用户名和密码', true)
      return
    }
    await ensureKey()
    const password_encrypted = await encryptPassword(form.value.password)
    await createUser({
      username: form.value.username.trim(),
      password_encrypted,
      role: form.value.role,
    })
    setMsg('用户创建成功')
    form.value = { username: '', password: '', role: 'user' }
    await loadUsers()
  } catch (e) {
    setMsg(e.message, true)
  }
}

function openReset(u) {
  resetUser.value = u
  resetPwd.value = ''
}

async function doReset() {
  if (!resetUser.value) return
  if (!resetPwd.value || resetPwd.value.length < 6) {
    setMsg('新密码至少 6 位', true)
    return
  }
  saving.value = true
  setMsg('')
  try {
    await ensureKey()
    const new_password_encrypted = await encryptPassword(resetPwd.value)
    await adminSetPassword({
      username: resetUser.value.username,
      new_password_encrypted,
    })
    setMsg(`已更新 ${resetUser.value.username} 的密码`)
    resetUser.value = null
    resetPwd.value = ''
  } catch (e) {
    setMsg(e.message, true)
  } finally {
    saving.value = false
  }
}

async function reseed() {
  working.value = true
  setMsg('')
  try {
    const token = localStorage.getItem('token')
    const res = await axios.post('/api/admin/seed?force=true', null, {
      headers: { Authorization: `Bearer ${token}` },
    })
    setMsg('种子数据完成：' + (res.data?.message || JSON.stringify(res.data)))
    await loadHealth()
  } catch (e) {
    setMsg(e.message, true)
  } finally {
    working.value = false
  }
}

async function ingestDocs() {
  working.value = true
  setMsg('')
  try {
    // empty paths → backend uses portable defaults (README.md + docs/)
    const res = await ingestReferences([])
    const n = res.indexed_count ?? 0
    const errN = (res.errors || []).length
    setMsg(`知识库导入完成：成功 ${n} 条` + (errN ? `，跳过 ${errN} 项` : ''))
    await loadHealth()
  } catch (e) {
    setMsg(e.message, true)
  } finally {
    working.value = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.admin-page {
  height: 100%;
  overflow: auto;
  padding: 28px 32px 40px;
  max-width: 1200px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
}

h1 {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.lead {
  margin-top: 6px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-top: 3px solid #ddd;
}

.stat.ok {
  border-top-color: #22a06b;
}

.stat.bad {
  border-top-color: #c9372c;
}

.stat.warn {
  border-top-color: #e2b203;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.stat-meta {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.35;
  word-break: break-all;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.85fr);
  gap: 16px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 22px;
}

.panel-head {
  margin-bottom: 14px;
}

h2 {
  font-size: 16px;
  font-weight: 650;
  margin-bottom: 4px;
}

.panel-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
}

.table-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 18px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}

th,
td {
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
}

th {
  background: #fafafa;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

tr:last-child td {
  border-bottom: none;
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
}

.col-action {
  width: 110px;
  text-align: right;
}

.role {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f3f3f3;
  color: #444;
}

.role.admin {
  background: #111;
  color: #fff;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 24px !important;
}

.create-box {
  border-top: 1px solid #f0f0f0;
  padding-top: 16px;
}

.create-box h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}

.create-form {
  display: grid;
  grid-template-columns: 1.2fr 1.2fr 0.9fr auto;
  gap: 10px;
}

.create-form input,
.create-form select,
.modal-card input {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13.5px;
  width: 100%;
  box-sizing: border-box;
}

.side-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kv {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kv > div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  align-items: baseline;
  font-size: 13.5px;
}

.kv dt {
  color: var(--text-muted);
  font-size: 12px;
}

.kv dd {
  margin: 0;
  font-weight: 500;
  word-break: break-word;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  background: #ccc;
  vertical-align: middle;
}

.dot.ok {
  background: #22a06b;
}

.dot.bad {
  background: #c9372c;
}

.actions-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

code {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 1px 5px;
  border-radius: 4px;
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 9px 14px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}

.btn:hover:not(:disabled) {
  background: #f7f7f8;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

.btn.primary:hover:not(:disabled) {
  background: #222;
}

.btn.sm {
  padding: 5px 10px;
  font-size: 12px;
}

.btn.block {
  width: 100%;
  text-align: center;
}

.toast {
  margin-top: 14px;
  font-size: 13px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f7f7f8;
  color: var(--text-secondary);
  line-height: 1.45;
}

.toast.err {
  background: #faf5f5;
  color: #a33;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}

.modal-card {
  width: min(400px, 100%);
  background: #fff;
  border-radius: 14px;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.12);
}

.modal-card h3 {
  font-size: 17px;
  font-weight: 650;
}

.modal-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: -6px;
}

.modal-card label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

@media (max-width: 960px) {
  .status-grid {
    grid-template-columns: 1fr 1fr;
  }

  .layout {
    grid-template-columns: 1fr;
  }

  .create-form {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .admin-page {
    padding: 20px 16px 32px;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .create-form {
    grid-template-columns: 1fr;
  }

  .page-head {
    flex-direction: column;
  }
}
</style>

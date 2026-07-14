<template>
  <div class="kb-page">
    <div class="toolbar">
      <input v-model="searchQuery" class="search" placeholder="搜索知识库..." @keydown.enter="load" />
      <select v-model="filterType" @change="load">
        <option value="">全部类型</option>
        <option value="研报">研报</option>
        <option value="新闻">新闻</option>
        <option value="公告">公告</option>
        <option value="自定义">自定义</option>
      </select>
      <button type="button" class="btn" @click="load">搜索</button>
      <button v-if="isAdmin" type="button" class="btn primary" @click="showAdd = true">添加文档</button>
      <button v-if="isAdmin" type="button" class="btn primary" @click="showImport = true">批量导入</button>
      <span class="count">共 {{ total }} 篇</span>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>标题</th>
            <th>类型</th>
            <th>来源 URL</th>
            <th>文件路径</th>
            <th>创建时间</th>
            <th v-if="isAdmin">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in documents" :key="row.id" @click="openDoc(row)">
            <td>{{ row.id }}</td>
            <td class="title">{{ row.title }}</td>
            <td>{{ row.doc_type }}</td>
            <td class="mono">{{ row.source_url || '-' }}</td>
            <td class="mono">{{ shortPath(row.file_path) }}</td>
            <td>{{ formatDate(row.created_at) }}</td>
            <td v-if="isAdmin" @click.stop>
              <button type="button" class="link" @click="remove(row)">删除</button>
            </td>
          </tr>
          <tr v-if="!documents.length">
            <td :colspan="isAdmin ? 7 : 6" class="empty">暂无文档</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showAdd" class="modal">
      <div class="modal-card">
        <h3>添加文档</h3>
        <label>标题<input v-model="form.title" /></label>
        <label>类型
          <select v-model="form.doc_type">
            <option>研报</option>
            <option>新闻</option>
            <option>公告</option>
            <option>自定义</option>
          </select>
        </label>
        <label>来源 URL<input v-model="form.source_url" placeholder="https:// 或 seed://" /></label>
        <label>内容<textarea v-model="form.content" rows="8" /></label>
        <div class="actions">
          <button type="button" class="btn" @click="showAdd = false">取消</button>
          <button type="button" class="btn primary" :disabled="saving" @click="addDoc">保存并索引</button>
        </div>
        <p v-if="msg" class="msg">{{ msg }}</p>
      </div>
    </div>

    <div v-if="showImport" class="modal">
      <div class="modal-card">
        <h3>批量导入（RAG）</h3>
        <p class="hint">支持 txt / md / csv 等文本文件，导入后自动切分并写入向量索引。</p>
        <label>文档类型
          <select v-model="importType">
            <option>自定义</option>
            <option>研报</option>
            <option>新闻</option>
            <option>公告</option>
          </select>
        </label>
        <label>统一来源 URL（可选）
          <input v-model="importUrl" placeholder="https://..." />
        </label>
        <input type="file" multiple @change="onFiles" />
        <div class="actions">
          <button type="button" class="btn" @click="showImport = false">取消</button>
          <button type="button" class="btn primary" :disabled="saving || !files.length" @click="doImport">
            导入 {{ files.length || '' }}
          </button>
        </div>
        <p v-if="msg" class="msg">{{ msg }}</p>
      </div>
    </div>

    <div v-if="detail" class="modal" @click.self="detail = null">
      <div class="modal-card wide">
        <h3>{{ detail.title }}</h3>
        <div class="meta">
          <span>{{ detail.doc_type }}</span>
          <span>{{ detail.source_url || '无 URL' }}</span>
        </div>
        <pre class="content">{{ detail.content }}</pre>
        <div class="actions">
          <button type="button" class="btn" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { kbList, kbAdd, kbDelete, kbGet, kbImport, searchKB } from '../api'

const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = computed(() => user.role === 'admin')
const documents = ref([])
const total = ref(0)
const searchQuery = ref('')
const filterType = ref('')
const showAdd = ref(false)
const showImport = ref(false)
const saving = ref(false)
const msg = ref('')
const detail = ref(null)
const files = ref([])
const importType = ref('自定义')
const importUrl = ref('')
const form = reactive({
  title: '',
  content: '',
  doc_type: '自定义',
  source_url: '',
})

function formatDate(v) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

function shortPath(p) {
  if (!p) return '-'
  const s = String(p)
  return s.length > 28 ? '...' + s.slice(-26) : s
}

async function load() {
  try {
    if (searchQuery.value.trim()) {
      const res = await searchKB({
        query: searchQuery.value.trim(),
        top_k: 20,
        doc_type: filterType.value || '全部',
      })
      documents.value = (res.data || []).map((d) => ({
        id: d.doc_id || d.id,
        title: d.title,
        doc_type: d.doc_type,
        source_url: d.source_url,
        file_path: d.file_path,
        created_at: '',
        content_preview: d.content,
      }))
      total.value = res.total || documents.value.length
    } else {
      const res = await kbList({
        doc_type: filterType.value || undefined,
        page: 1,
        page_size: 50,
      })
      documents.value = res.data || []
      total.value = res.total || 0
    }
  } catch (e) {
    msg.value = e.message
  }
}

async function addDoc() {
  saving.value = true
  msg.value = ''
  try {
    await kbAdd({ ...form })
    showAdd.value = false
    form.title = ''
    form.content = ''
    form.source_url = ''
    await load()
  } catch (e) {
    msg.value = e.message
  } finally {
    saving.value = false
  }
}

function onFiles(e) {
  files.value = Array.from(e.target.files || [])
}

async function doImport() {
  if (!files.value.length) return
  saving.value = true
  msg.value = ''
  try {
    const fd = new FormData()
    files.value.forEach((f) => fd.append('files', f))
    fd.append('doc_type', importType.value)
    fd.append('source_url', importUrl.value || '')
    const res = await kbImport(fd)
    msg.value = `导入完成: ${res.imported}/${res.total}`
    showImport.value = false
    files.value = []
    await load()
  } catch (e) {
    msg.value = e.message
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!confirm('确认删除文档 ' + row.id + ' ?')) return
  await kbDelete(row.id)
  await load()
}

async function openDoc(row) {
  try {
    detail.value = await kbGet(row.id)
  } catch {
    detail.value = {
      title: row.title,
      doc_type: row.doc_type,
      source_url: row.source_url,
      content: row.content_preview || '',
    }
  }
}

onMounted(load)
</script>

<style scoped>
.kb-page {
  height: 100%;
  overflow: auto;
  padding: 20px 24px;
}

.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.search {
  width: 240px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
}

select,
input,
textarea {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

.count {
  margin-left: auto;
  color: var(--text-muted);
  font-size: 13px;
}

.table-wrap {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: auto;
  background: #fff;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

th {
  background: #fafafa;
  font-weight: 600;
  color: var(--text-secondary);
}

tr:hover td {
  background: #fafafa;
  cursor: pointer;
}

.title {
  font-weight: 500;
  max-width: 280px;
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 200px;
  word-break: break-all;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px !important;
}

.link {
  border: none;
  background: none;
  color: #666;
  text-decoration: underline;
  cursor: pointer;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-card {
  width: min(520px, 92vw);
  background: #fff;
  border-radius: 14px;
  padding: 22px;
  border: 1px solid var(--border);
}

.modal-card.wide {
  width: min(720px, 94vw);
}

.modal-card h3 {
  margin-bottom: 14px;
}

.modal-card label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.modal-card input,
.modal-card textarea,
.modal-card select {
  width: 100%;
  margin-top: 6px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.msg {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.content {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  max-height: 50vh;
  overflow: auto;
  background: #fafafa;
  padding: 12px;
  border-radius: 8px;
}
</style>

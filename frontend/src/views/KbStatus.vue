<template>
  <div class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>知识库状态</h2>
          <p class="sub">查看向量索引可用性、文档来源 URL 与访问状态</p>
        </div>
        <button type="button" class="btn" :disabled="loading" @click="load">刷新状态</button>
      </div>

      <div v-if="msg" class="msg err">{{ msg }}</div>

      <div class="summary">
        <div class="stat">
          <span>向量索引</span>
          <strong>
            <i class="dot" :class="usable ? 'ok' : 'bad'" />
            {{ usable ? '可用' : '不可用' }}
          </strong>
        </div>
        <div class="stat">
          <span>文档数</span>
          <strong>{{ vector.document_count ?? '-' }}</strong>
        </div>
        <div class="stat">
          <span>分块数</span>
          <strong>{{ vector.chunk_count ?? '-' }}</strong>
        </div>
        <div class="stat">
          <span>嵌入服务</span>
          <strong>
            <i class="dot" :class="embedOk ? 'ok' : 'bad'" />
            {{ embedOk ? '在线' : '离线' }}
          </strong>
        </div>
        <div class="stat">
          <span>RAG 开关</span>
          <strong>{{ ragEnabled ? '已启用' : '已关闭' }}</strong>
        </div>
        <div class="stat wide">
          <span>向量库路径</span>
          <strong class="mono">{{ vector.path || '-' }}</strong>
        </div>
      </div>

      <div v-if="embedding.models?.length" class="models">
        <span class="label">可用模型</span>
        <span v-for="m in embedding.models" :key="m" class="tag">{{ m }}</span>
      </div>

      <h3>知识库来源</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>文档 ID</th>
              <th>标题</th>
              <th>类型</th>
              <th>来源 URL</th>
              <th>文件路径</th>
              <th>分块</th>
              <th>可访问</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in sources" :key="s.doc_id">
              <td>{{ s.doc_id }}</td>
              <td class="title">{{ s.title || '-' }}</td>
              <td>{{ s.doc_type || '-' }}</td>
              <td class="mono">{{ s.source_url || '-' }}</td>
              <td class="mono">{{ shortPath(s.file_path) }}</td>
              <td>{{ s.chunk_count ?? '-' }}</td>
              <td>
                <i class="dot" :class="s.reachable ? 'ok' : 'warn'" />
                {{ s.reachable ? '是' : '否' }}
              </td>
              <td class="detail">{{ s.detail || s.kind || '-' }}</td>
            </tr>
            <tr v-if="!sources.length && !loading">
              <td colspan="8" class="empty">暂无知识库来源，请先在「知识库」中添加或导入文档</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { kbStatus } from '../api'

const loading = ref(false)
const msg = ref('')
const data = ref(null)

const vector = computed(() => data.value?.vector_store || {})
const embedding = computed(() => data.value?.embedding || {})
const sources = computed(() => data.value?.sources || [])
const usable = computed(() => !!vector.value.usable)
const embedOk = computed(() => !!embedding.value.reachable)
const ragEnabled = computed(() => !!data.value?.rag_enabled)

function shortPath(p) {
  if (!p) return '-'
  const s = String(p)
  return s.length > 36 ? '...' + s.slice(-34) : s
}

async function load() {
  loading.value = true
  msg.value = ''
  try {
    data.value = await kbStatus()
  } catch (e) {
    msg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page {
  height: 100%;
  overflow: auto;
  padding: 24px;
}

.card {
  max-width: 1100px;
  margin: 0 auto;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
  padding: 24px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
}

h2 {
  font-size: 18px;
  font-weight: 600;
}

h3 {
  font-size: 14px;
  margin: 24px 0 12px;
}

.sub {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.msg {
  margin-bottom: 14px;
  font-size: 13px;
  padding: 10px 12px;
  border-radius: 8px;
}

.msg.err {
  color: #a33;
  background: #faf5f5;
}

.summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat.wide {
  grid-column: 1 / -1;
}

.stat span {
  font-size: 12px;
  color: var(--text-muted);
}

.stat strong {
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px !important;
  font-weight: 500 !important;
  word-break: break-all;
}

.models {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.models .label {
  font-size: 12px;
  color: var(--text-muted);
  margin-right: 4px;
}

.tag {
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  color: var(--text-secondary);
}

.table-wrap {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 12px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

th {
  background: #fafafa;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}

.title {
  max-width: 220px;
}

.detail {
  color: var(--text-muted);
  font-size: 12px;
  max-width: 160px;
}

.empty {
  text-align: center;
  color: var(--text-muted);
  padding: 36px !important;
}

td .dot {
  margin-right: 4px;
}

@media (max-width: 900px) {
  .summary {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

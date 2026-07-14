<template>
  <div class="page">
    <div class="card">
      <div class="card-head">
        <div>
          <h2>RAG 参数</h2>
          <p class="sub">调整检索增强生成相关参数，影响知识库检索与问答质量</p>
        </div>
        <button type="button" class="btn" :disabled="loading" @click="load">刷新</button>
      </div>

      <div v-if="msg" class="msg" :class="{ err: isError }">{{ msg }}</div>

      <div class="form">
        <label class="row">
          <span class="label">启用 RAG</span>
          <input type="checkbox" v-model="form.enabled" :disabled="!isAdmin || saving" />
        </label>

        <label class="row">
          <span class="label">Top K</span>
          <div class="control">
            <input type="number" min="1" max="50" v-model.number="form.top_k" :disabled="!isAdmin || saving" />
            <span class="hint">检索返回的最大片段数</span>
          </div>
        </label>

        <label class="row">
          <span class="label">切分策略</span>
          <div class="control">
            <select v-model="form.chunk_strategy" :disabled="!isAdmin || saving">
              <option value="sentence">按句子（推荐）— 优先在句号/问号/换行处切分</option>
              <option value="paragraph">按段落 — 空行分段后再合并到块大小</option>
              <option value="markdown">按 Markdown 标题 — 以 #/## 标题为边界</option>
              <option value="fixed">固定长度 — 纯字符滑窗切分</option>
              <option value="custom">自定义分隔符 — 使用下方正则</option>
            </select>
            <span class="hint">{{ strategyHint }}</span>
          </div>
        </label>

        <label v-if="form.chunk_strategy === 'custom'" class="row">
          <span class="label">自定义分隔符</span>
          <div class="control">
            <input
              type="text"
              v-model="form.chunk_separator"
              placeholder="正则，如 \\n\\n+ 或 \\|\\|"
              :disabled="!isAdmin || saving"
            />
            <span class="hint">按正则切开后再按块大小合并；留空则回退为按句子</span>
          </div>
        </label>

        <label class="row">
          <span class="label">块大小</span>
          <div class="control">
            <input type="number" min="100" max="4000" step="50" v-model.number="form.chunk_size" :disabled="!isAdmin || saving" />
            <span class="hint">单个分块目标字符数</span>
          </div>
        </label>

        <label class="row">
          <span class="label">块重叠</span>
          <div class="control">
            <input type="number" min="0" max="1000" step="10" v-model.number="form.chunk_overlap" :disabled="!isAdmin || saving" />
            <span class="hint">相邻分块重叠字符数，减少断句信息丢失</span>
          </div>
        </label>

        <label class="row">
          <span class="label">Score Threshold</span>
          <div class="control">
            <input type="number" min="0" max="1" step="0.05" v-model.number="form.score_threshold" :disabled="!isAdmin || saving" />
            <span class="hint">相似度阈值，低于该值的结果将被过滤</span>
          </div>
        </label>

        <label class="row">
          <span class="label">Embedding 模型</span>
          <div class="control">
            <input type="text" v-model="form.embedding_model" placeholder="默认使用服务端配置" :disabled="!isAdmin || saving" />
            <span class="hint">留空则使用环境变量中的嵌入模型</span>
          </div>
        </label>
      </div>

      <div class="actions">
        <button v-if="isAdmin" type="button" class="btn primary" :disabled="saving || loading" @click="save">
          {{ saving ? '保存中...' : '保存参数' }}
        </button>
        <p v-else class="readonly">当前为普通用户，仅可查看参数，修改需管理员权限</p>
      </div>

      <div v-if="store" class="store">
        <h3>当前向量库</h3>
        <div class="grid">
          <div class="item"><span>文档数</span><strong>{{ store.document_count ?? '-' }}</strong></div>
          <div class="item"><span>分块数</span><strong>{{ store.chunk_count ?? '-' }}</strong></div>
          <div class="item wide"><span>存储路径</span><strong class="mono">{{ store.path || '-' }}</strong></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getRagParams, updateRagParams } from '../api'

const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = computed(() => user.role === 'admin')
const loading = ref(false)
const saving = ref(false)
const msg = ref('')
const isError = ref(false)
const store = ref(null)
const form = reactive({
  enabled: true,
  top_k: 5,
  chunk_size: 800,
  chunk_overlap: 120,
  score_threshold: 0.15,
  embedding_model: '',
  chunk_strategy: 'sentence',
  chunk_separator: '',
})

const strategyHint = computed(() => {
  const map = {
    sentence: '适合中文研报/新闻：尽量在完整句边界切分，再合并到设定块大小。',
    paragraph: '适合分段清晰的长文：先按空行分段，再合并。',
    markdown: '适合 Markdown 文档：以标题作为自然切分点。',
    fixed: '不关心语义边界，严格按字符数滑窗切分。',
    custom: '使用你提供的正则作为切分点，适合特殊格式文本。',
  }
  return map[form.chunk_strategy] || ''
})

async function load() {
  loading.value = true
  msg.value = ''
  isError.value = false
  try {
    const res = await getRagParams()
    Object.assign(form, {
      enabled: res.params?.enabled ?? true,
      top_k: res.params?.top_k ?? 5,
      chunk_size: res.params?.chunk_size ?? 800,
      chunk_overlap: res.params?.chunk_overlap ?? 120,
      score_threshold: res.params?.score_threshold ?? 0.15,
      embedding_model: res.params?.embedding_model || '',
      chunk_strategy: res.params?.chunk_strategy || 'sentence',
      chunk_separator: res.params?.chunk_separator || '',
    })
    store.value = res.store || null
  } catch (e) {
    isError.value = true
    msg.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!isAdmin.value) return
  saving.value = true
  msg.value = ''
  isError.value = false
  try {
    const payload = {
      enabled: form.enabled,
      top_k: form.top_k,
      chunk_size: form.chunk_size,
      chunk_overlap: form.chunk_overlap,
      score_threshold: form.score_threshold,
      embedding_model: form.embedding_model || null,
      chunk_strategy: form.chunk_strategy,
      chunk_separator: form.chunk_separator || '',
    }
    const res = await updateRagParams(payload)
    Object.assign(form, {
      ...form,
      ...(res.params || {}),
      embedding_model: res.params?.embedding_model || '',
      chunk_strategy: res.params?.chunk_strategy || form.chunk_strategy,
      chunk_separator: res.params?.chunk_separator || '',
    })
    msg.value = '参数已保存（新导入/重建的文档会使用新切分策略）'
  } catch (e) {
    isError.value = true
    msg.value = e.message || '保存失败'
  } finally {
    saving.value = false
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
  max-width: 760px;
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

.sub {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 16px;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.label {
  font-size: 14px;
  color: var(--text);
  font-weight: 500;
}

.control {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.control input[type='number'],
.control input[type='text'],
.control select {
  width: min(420px, 100%);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  background: #fff;
}

.control input[type='checkbox'] {
  width: 16px;
  height: 16px;
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
}

.actions {
  margin-top: 20px;
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.readonly {
  font-size: 13px;
  color: var(--text-muted);
}

.msg {
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 8px;
}

.msg.err {
  color: #a33;
  background: #faf5f5;
}

.store {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.store h3 {
  font-size: 14px;
  margin-bottom: 12px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.item {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.item.wide {
  grid-column: 1 / -1;
}

.item span {
  font-size: 12px;
  color: var(--text-muted);
}

.item strong {
  font-size: 15px;
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px !important;
  word-break: break-all;
  font-weight: 500 !important;
}

@media (max-width: 640px) {
  .row {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>

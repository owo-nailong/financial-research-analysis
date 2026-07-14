<template>
  <div class="ma-page">
    <div class="intro">
      <h2>多智能体协调</h2>
      <p>
        参考 LangGraph 协作流程：资深金融分析师、普通投资者视角、审核员、经理综合依次工作，
        降低单一模型回答的片面性。本地 Ollama 将连续调用多次，请预留约 1–3 分钟。
      </p>
    </div>

    <div class="form">
      <label>
        关注标的代码（可选）
        <input v-model="stockCode" placeholder="例: 600519" maxlength="10" />
      </label>
      <label>
        问题
        <textarea v-model="question" rows="4" placeholder="例如：综合分析贵州茅台当前投资价值与主要风险" />
      </label>
      <div class="check-row">
        <input id="use-rag" type="checkbox" v-model="useRag" class="check-input" />
        <label for="use-rag" class="check-label">使用知识库检索作为参考资料</label>
      </div>
      <button type="button" class="btn primary" :disabled="loading || !question.trim()" @click="run">
        {{ loading ? '多智能体运行中...' : '开始协调分析' }}
      </button>
      <p v-if="err" class="err">{{ err }}</p>
    </div>

    <div v-if="result" class="result">
      <div class="roles">
        参与角色：{{ (result.roles || []).join(' → ') }}
      </div>
      <div v-for="(step, i) in result.steps || []" :key="i" class="step">
        <div class="step-head">
          <span class="badge">{{ i + 1 }}</span>
          <strong>{{ step.role_name || step.role }}</strong>
        </div>
        <div class="markdown-body" v-html="md(step.output)" />
      </div>
      <div class="final">
        <h3>最终综合答复</h3>
        <div class="markdown-body" v-html="md(result.final_answer)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { marked } from 'marked'
import { multiAgentRun, searchKB } from '../api'

const question = ref('综合分析贵州茅台（600519）当前投资价值、机构观点与主要风险')
const stockCode = ref('600519')
const useRag = ref(true)
const loading = ref(false)
const err = ref('')
const result = ref(null)

function md(t) {
  return marked.parse(t || '', { breaks: true })
}

async function run() {
  loading.value = true
  err.value = ''
  result.value = null
  try {
    let context = ''
    if (useRag.value) {
      try {
        const kb = await searchKB({
          query: question.value,
          top_k: 5,
          stock_code: stockCode.value || undefined,
        })
        context = (kb.data || [])
          .map((d) => `[${d.title}|${d.source_url || ''}]\n${(d.content || '').slice(0, 600)}`)
          .join('\n---\n')
      } catch {
        /* ignore rag failure */
      }
    }
    result.value = await multiAgentRun({
      question: question.value.trim(),
      stock_code: stockCode.value || null,
      context: context || null,
    })
  } catch (e) {
    err.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ma-page {
  height: 100%;
  overflow: auto;
  padding: 24px;
  max-width: 900px;
}

.intro h2 {
  font-size: 20px;
  margin-bottom: 8px;
}

.intro p {
  color: var(--text-secondary);
  line-height: 1.65;
  margin-bottom: 18px;
  font-size: 14px;
}

.form label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.form input[type='text'],
.form input:not([type]),
.form textarea {
  display: block;
  width: 100%;
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  box-sizing: border-box;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0 16px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fafafa;
  width: fit-content;
  max-width: 100%;
}

.check-input {
  width: 16px !important;
  height: 16px !important;
  margin: 0 !important;
  flex-shrink: 0;
  accent-color: #111;
  cursor: pointer;
}

.check-label {
  margin: 0 !important;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  line-height: 1.4;
  white-space: normal;
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
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

.err {
  margin-top: 10px;
  color: #a33;
  font-size: 13px;
}

.result {
  margin-top: 24px;
}

.roles {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.step {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fff;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.badge {
  display: inline-flex;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #111;
  color: #fff;
  font-size: 12px;
  align-items: center;
  justify-content: center;
}

.final {
  margin-top: 20px;
  border: 1px solid #111;
  border-radius: 12px;
  padding: 16px;
  background: #fafafa;
}

.final h3 {
  margin-bottom: 10px;
  font-size: 16px;
}
</style>

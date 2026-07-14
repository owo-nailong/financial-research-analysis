<template>
  <div class="wb-page">
    <div class="layout">
      <section class="panel">
        <h3>内容配置</h3>
        <label>内容类型
          <select v-model="config.contentType">
            <option value="研报摘要">研报摘要</option>
            <option value="投资建议">投资建议书</option>
            <option value="行业分析">行业分析报告</option>
            <option value="市场简报">每日市场简报</option>
            <option value="自定义">自定义</option>
          </select>
        </label>
        <label>
          关注标的代码
          <input v-model="config.stockCode" placeholder="例: 600519" />
          <span class="field-hint">A股六位代码，用于绑定生成内容与知识库标签</span>
        </label>
        <label>股票名称<input v-model="config.stockName" placeholder="贵州茅台" /></label>
        <label>模板
          <select v-model="config.templateId">
            <option :value="null">默认</option>
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </label>
        <label v-if="config.contentType === '自定义'">额外要求
          <textarea v-model="config.customPrompt" rows="3" />
        </label>
        <button class="btn primary" type="button" :disabled="generating" @click="generate">
          {{ generating ? '生成中...' : '开始生成' }}
        </button>
        <button class="btn" type="button" :disabled="generating" @click="portfolio">批量组合分析</button>
      </section>

      <section class="output">
        <div class="out-head">
          <h3>生成结果</h3>
          <div class="out-actions">
            <button v-if="result" type="button" class="btn sm" @click="copy">复制</button>
            <button v-if="result" type="button" class="btn sm" @click="download">下载 Markdown</button>
            <button
              v-if="result && isAdmin"
              type="button"
              class="btn sm primary"
              :disabled="savingKb"
              @click="saveToKb"
            >
              {{ savingKb ? '入库中...' : '存入知识库' }}
            </button>
          </div>
        </div>
        <p v-if="msg" class="msg">{{ msg }}</p>
        <div v-if="!result" class="placeholder">选择参数后生成投资内容</div>
        <div v-else class="markdown-body" v-html="rendered" />
        <p v-if="result && !isAdmin" class="tip">提示：存入知识库需要管理员账号；你仍可复制或下载文件。</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { marked } from 'marked'
import { generateContent, batchPortfolio, templateList, kbAdd } from '../api'

const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = user.role === 'admin'

const config = reactive({
  contentType: '研报摘要',
  stockCode: '600519',
  stockName: '贵州茅台',
  templateId: null,
  customPrompt: '',
})
const templates = ref([])
const generating = ref(false)
const savingKb = ref(false)
const result = ref('')
const msg = ref('')
const rendered = computed(() => marked.parse(result.value || '', { breaks: true }))

async function loadTemplates() {
  try {
    const res = await templateList()
    templates.value = res.data || []
  } catch {
    templates.value = []
  }
}

async function generate() {
  generating.value = true
  msg.value = ''
  try {
    const res = await generateContent({
      content_type: config.contentType,
      stock_code: config.stockCode || null,
      stock_name: config.stockName || null,
      template_id: config.templateId || null,
      extra_params: config.customPrompt ? { note: config.customPrompt } : null,
    })
    result.value = res.generated_content || JSON.stringify(res, null, 2)
  } catch (e) {
    result.value = '生成失败: ' + e.message
  } finally {
    generating.value = false
  }
}

async function portfolio() {
  generating.value = true
  msg.value = ''
  try {
    const res = await batchPortfolio({
      stocks: [
        { code: '600519', name: '贵州茅台' },
        { code: '300750', name: '宁德时代' },
        { code: '002594', name: '比亚迪' },
      ],
      days: 30,
    })
    result.value = '```json\n' + JSON.stringify(res, null, 2) + '\n```'
  } catch (e) {
    result.value = '分析失败: ' + e.message
  } finally {
    generating.value = false
  }
}

function copy() {
  navigator.clipboard.writeText(result.value || '')
  msg.value = '已复制到剪贴板'
}

function download() {
  const text = result.value || ''
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  const name = `${config.contentType}_${config.stockCode || 'content'}_${Date.now()}.md`
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
  msg.value = '已开始下载: ' + name
}

async function saveToKb() {
  if (!isAdmin || !result.value) return
  savingKb.value = true
  msg.value = ''
  try {
    const title = `${config.contentType}-${config.stockName || config.stockCode || '未命名'}-${new Date().toISOString().slice(0, 10)}`
    await kbAdd({
      title,
      content: result.value,
      doc_type: '自定义',
      tags: [config.contentType, config.stockCode].filter(Boolean),
      related_stocks: config.stockCode ? [config.stockCode] : [],
      source_url: 'workbench://generated',
    })
    msg.value = '已存入知识库并参与 RAG 索引'
  } catch (e) {
    msg.value = '入库失败: ' + e.message
  } finally {
    savingKb.value = false
  }
}

onMounted(loadTemplates)
</script>

<style scoped>
.wb-page {
  height: 100%;
  overflow: auto;
  padding: 20px 24px;
}

.layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  min-height: calc(100% - 8px);
}

.panel,
.output {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  padding: 18px;
}

h3 {
  font-size: 15px;
  margin-bottom: 14px;
}

label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.field-hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

input,
select,
textarea {
  display: block;
  width: 100%;
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
}

.btn {
  width: 100%;
  margin-top: 8px;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

.btn.sm {
  width: auto;
  margin: 0;
  padding: 6px 12px;
  font-size: 12px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.out-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.out-head h3 {
  margin: 0;
}

.out-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.placeholder {
  color: var(--text-muted);
  padding: 40px 0;
  text-align: center;
}

.msg {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>

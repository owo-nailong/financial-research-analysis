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
        <label>股票代码<input v-model="config.stockCode" placeholder="600519" /></label>
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
          <button v-if="result" type="button" class="btn" @click="copy">复制</button>
        </div>
        <div v-if="!result" class="placeholder">选择参数后生成投资内容</div>
        <div v-else class="markdown-body" v-html="rendered" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { marked } from 'marked'
import { generateContent, batchPortfolio, templateList } from '../api'

const config = reactive({
  contentType: '研报摘要',
  stockCode: '600519',
  stockName: '贵州茅台',
  templateId: null,
  customPrompt: '',
})
const templates = ref([])
const generating = ref(false)
const result = ref('')
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

.out-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.out-head .btn {
  width: auto;
  margin: 0;
  padding: 6px 12px;
}

.placeholder {
  color: var(--text-muted);
  padding: 40px 0;
  text-align: center;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>

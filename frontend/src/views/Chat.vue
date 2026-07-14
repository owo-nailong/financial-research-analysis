<template>
  <div class="chat-page">
    <div class="chat-body" ref="scrollRef">
      <div v-if="messages.length === 0" class="empty">
        <h2>Ready when you are.</h2>
        <p class="empty-desc">分析研报、对比观点、提取财务数据、回答投资问题</p>
        <div class="composer center">
          <div class="composer-inner">
            <input
              v-model="input"
              class="ask"
              placeholder="Ask anything"
              @keydown.enter.exact.prevent="send"
            />
            <button class="send" type="button" :disabled="!input.trim() || loading" @click="send">
              发送
            </button>
          </div>
          <div class="composer-tools">
            <label class="check" title="开启后会从知识库检索相关片段再回答">
              <input type="checkbox" v-model="useRag" />
              启用知识库检索
            </label>
            <div class="stock-field">
              <label class="stock-label">
                关注标的代码
                <span
                  class="help"
                  title="「关注标的代码」指股票的交易所代码（不是用户账号）。填了之后，快捷分析与工具会优先查该股票的研报、评级与情绪；不填也可以直接用自然语言提问。例：600519=贵州茅台。"
                >?</span>
              </label>
              <input
                v-model="stockCode"
                class="stock"
                placeholder="例: 600519"
                maxlength="10"
              />
            </div>
          </div>
          <div class="suggestions">
            <button
              v-for="s in suggestions"
              :key="s"
              type="button"
              class="chip"
              @click="useSuggestion(s)"
            >
              {{ s }}
            </button>
          </div>
        </div>
      </div>

      <template v-else>
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="avatar">{{ m.role === 'user' ? 'U' : 'AI' }}</div>
          <div class="bubble">
            <div v-if="m.thoughtChain?.length" class="thought">
              <details>
                <summary>推理过程</summary>
                <div v-for="(step, si) in m.thoughtChain" :key="si" class="step">
                  <template v-if="step.type === 'action'">
                    调用工具: {{ step.tool }}
                    <div class="muted">{{ step.tool_input }}</div>
                  </template>
                  <template v-else-if="step.type === 'observation'">
                    观察: {{ step.tool }}
                    <div class="muted">{{ (step.output || '').slice(0, 240) }}</div>
                  </template>
                  <template v-else>完成</template>
                </div>
              </details>
            </div>
            <div class="markdown-body" v-html="renderMd(m.content)" />
            <div v-if="displaySources(m.sources).length" class="sources">
              <span class="src-label">来源</span>
              <span
                v-for="(s, si) in displaySources(m.sources)"
                :key="si"
                class="src-tag"
                :class="s.kind"
                :title="s.hint || s.label"
              >
                {{ s.label }}
              </span>
            </div>
          </div>
        </div>
        <div v-if="loading" class="msg assistant">
          <div class="avatar">AI</div>
          <div class="bubble muted">正在分析...</div>
        </div>
      </template>
    </div>

    <div v-if="messages.length > 0" class="composer bottom">
      <div class="composer-inner">
        <input
          v-model="input"
          class="ask"
          placeholder="Ask anything"
          :disabled="loading"
          @keydown.enter.exact.prevent="send"
        />
        <button class="send" type="button" :disabled="!input.trim() || loading" @click="send">
          发送
        </button>
      </div>
      <div class="composer-tools">
        <label class="check" title="开启后会从知识库检索相关片段再回答">
          <input type="checkbox" v-model="useRag" />
          启用知识库检索
        </label>
        <div class="stock-field">
          <label class="stock-label">
            关注标的代码
            <span
              class="help"
              title="「关注标的代码」指股票的交易所代码（不是用户账号）。填了之后，快捷分析与工具会优先查该股票的研报、评级与情绪；不填也可以直接用自然语言提问。"
            >?</span>
          </label>
          <input v-model="stockCode" class="stock" placeholder="例: 600519" maxlength="10" />
        </div>
        <button type="button" class="ghost" @click="clearChat">清除会话</button>
        <button
          type="button"
          class="ghost"
          :disabled="!stockCode || loading"
          :title="stockCode ? '一键拉取该股票的情绪、评级与观点对比' : '请先填写关注标的代码'"
          @click="runQuick"
        >
          快捷分析该标的
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { marked } from 'marked'
import { agentChat, clearSession, quickReport } from '../api'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const useRag = ref(true)
const stockCode = ref('')
const sessionId = ref('session_' + Date.now())
const scrollRef = ref(null)

const suggestions = [
  '分析贵州茅台最近的市场情绪',
  '对比宁德时代的券商研报观点',
  '提取比亚迪财务与评级数据',
  '白酒行业有哪些主要风险提示',
]

function renderMd(text) {
  return marked.parse(text || '', { breaks: true })
}

/** 用来源标题展示，避免一堆重复的 "rag" 标签 */
function displaySources(list) {
  if (!Array.isArray(list) || !list.length) return []
  const seen = new Set()
  const out = []
  for (const s of list) {
    const title = (s?.title || '').trim()
    const tool = (s?.tool || '').trim()
    // 文档类：优先标题；工具类：用中文名/title
    let label = title
    if (!label || label.toLowerCase() === 'rag' || label === 'search_knowledge_base') {
      if (tool === 'rag' || tool === 'search_knowledge_base') continue
      label = title || tool || ''
    }
    if (!label || label.toLowerCase() === 'rag') continue
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push({
      label: label.length > 28 ? label.slice(0, 26) + '…' : label,
      kind: s.kind === 'document' || tool === 'rag' ? 'doc' : 'tool',
      hint: [title, s.source_url, tool].filter(Boolean).join(' · '),
    })
    if (out.length >= 8) break
  }
  return out
}

async function scrollBottom() {
  await nextTick()
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

function useSuggestion(s) {
  input.value = s
  send()
}

async function send() {
  const q = input.value.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true
  await scrollBottom()
  try {
    const res = await agentChat({
      question: q,
      session_id: sessionId.value,
      stock_code: stockCode.value || null,
      use_rag: useRag.value,
    })
    messages.value.push({
      role: 'assistant',
      content: res.answer || '',
      thoughtChain: res.thought_chain || [],
      sources: res.sources || [],
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败: ' + e.message })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

async function clearChat() {
  try {
    await clearSession(sessionId.value)
  } catch {
    /* ignore */
  }
  sessionId.value = 'session_' + Date.now()
  messages.value = []
}

async function runQuick() {
  if (!stockCode.value) return
  loading.value = true
  messages.value.push({ role: 'user', content: `快捷分析 ${stockCode.value}` })
  try {
    const res = await quickReport(stockCode.value)
    messages.value.push({
      role: 'assistant',
      content: '```json\n' + JSON.stringify(res, null, 2) + '\n```',
      sources: [{ tool: 'quick-report' }],
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '快捷分析失败: ' + e.message })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}
</script>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px 12px;
}

.empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-bottom: 8vh;
}

.empty h2 {
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-bottom: 8px;
}

.empty-desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 28px;
}

.composer {
  width: min(760px, 100%);
}

.composer.center {
  margin: 0 auto;
}

.composer.bottom {
  margin: 0 auto 18px;
  width: min(760px, calc(100% - 32px));
}

.composer-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 10px 8px 18px;
  background: #fff;
  box-shadow: var(--shadow);
}

.ask {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  background: transparent;
  min-width: 0;
}

.send {
  border: none;
  background: #111;
  color: #fff;
  border-radius: 999px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
}

.send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.composer-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.check {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.stock-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stock-label {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid #ccc;
  font-size: 10px;
  color: #888;
  cursor: help;
}

.stock {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  width: 110px;
}

.ghost {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  color: var(--text-secondary);
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 18px;
}

.chip {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

.chip:hover {
  background: #f7f7f8;
}

.msg {
  display: flex;
  gap: 14px;
  width: min(760px, 100%);
  margin: 0 auto 22px;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: #111;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg.user .avatar {
  background: #ececec;
  color: #111;
}

.bubble {
  flex: 1;
  min-width: 0;
  padding-top: 4px;
}

.thought {
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.thought summary {
  cursor: pointer;
}

.step {
  margin-top: 6px;
  padding-left: 8px;
  border-left: 2px solid #eee;
}

.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.sources {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.src-label {
  font-size: 12px;
  color: var(--text-muted);
}

.src-tag {
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--text-secondary);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.src-tag.doc {
  background: #f7f7f8;
}

.src-tag.tool {
  background: #fff;
}
</style>

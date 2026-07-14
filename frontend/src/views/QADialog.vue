<template>
  <div class="qa-page">
    <!-- 顶部操作栏 -->
    <el-card class="qa-toolbar" shadow="never">
      <el-row :gutter="16" align="middle">
        <el-col :span="4">
          <el-input
            v-model="stockCode"
            placeholder="股票代码 (如 600519)"
            clearable
            size="default"
          >
            <template #prepend>🔍</template>
          </el-input>
        </el-col>
        <el-col :span="2">
          <el-button type="primary" :loading="loading" @click="handleQuickReport" :disabled="!stockCode">
            快捷分析
          </el-button>
        </el-col>
        <el-col :span="2">
          <el-select v-model="sessionId" size="default" placeholder="会话" style="width:100%">
            <el-option label="会话 1" value="session_1" />
            <el-option label="会话 2" value="session_2" />
            <el-option label="新会话" value="new" />
          </el-select>
        </el-col>
        <el-col :span="2">
          <el-button text type="danger" @click="handleClearSession">清除会话</el-button>
        </el-col>
        <el-col :span="4" :offset="10">
          <div class="toolbar-tip">
            💡 试试问: "分析贵州茅台最近的市场情绪" 或 "对比宁德时代的券商观点"
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 对话区 -->
    <div class="qa-chat-area" ref="chatArea">
      <div v-if="messages.length === 0" class="qa-welcome">
        <div class="welcome-icon">📊</div>
        <h2>金融研报智能分析助手</h2>
        <p>我可以帮您: 分析市场情绪 · 对比券商观点 · 提取财务数据 · 生成研报摘要 · 回答投资问题</p>
        <div class="suggestion-chips">
          <el-tag
            v-for="q in suggestions"
            :key="q"
            class="suggestion-chip"
            @click="handleSuggestion(q)"
          >
            {{ q }}
          </el-tag>
        </div>
      </div>

      <div v-for="(msg, idx) in messages" :key="idx" class="qa-message">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="message-row user-row">
          <div class="message-bubble user-bubble">
            <div class="bubble-text">{{ msg.content }}</div>
          </div>
          <el-avatar :size="36" class="message-avatar">👤</el-avatar>
        </div>

        <!-- AI 消息 -->
        <div v-else class="message-row ai-row">
          <el-avatar :size="36" class="message-avatar" style="background: linear-gradient(135deg, #409EFF, #337ECC)">🤖</el-avatar>
          <div class="message-bubble ai-bubble">
            <!-- 思考链（可折叠） -->
            <el-collapse v-if="msg.thoughtChain && msg.thoughtChain.length" class="thought-collapse">
              <el-collapse-item title="🧠 推理过程">
                <div v-for="(step, si) in msg.thoughtChain" :key="si" class="thought-step">
                  <template v-if="step.type === 'action'">
                    <div class="thought-action">🔧 调用工具: <strong>{{ step.tool }}</strong></div>
                    <div class="thought-input">输入: {{ step.tool_input }}</div>
                    <div v-if="step.output" class="thought-output">输出: {{ step.output?.substring(0, 500) }}...</div>
                  </template>
                  <template v-else>
                    <div class="thought-finish">✅ 生成最终回答</div>
                  </template>
                </div>
              </el-collapse-item>
            </el-collapse>

            <!-- 实际回答（Markdown 渲染） -->
            <div class="bubble-text markdown-body" v-html="renderMarkdown(msg.content)"></div>

            <!-- 引用来源 -->
            <div v-if="msg.sources && msg.sources.length" class="source-tags">
              <span class="source-label">📚 参考来源:</span>
              <el-tag v-for="(s, si) in msg.sources" :key="si" size="small" type="info" class="source-tag">
                {{ s.tool }}
              </el-tag>
            </div>

            <!-- 操作按钮 -->
            <div class="message-actions">
              <el-button text size="small" @click="copyText(msg.content)">
                <el-icon><CopyDocument /></el-icon> 复制
              </el-button>
              <el-button text size="small" @click="handleFeedback(msg, '有用')">
                👍 有用
              </el-button>
              <el-button text size="small" @click="handleFeedback(msg, '无用')">
                👎 无用
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载动画 -->
      <div v-if="loading" class="message-row ai-row">
        <el-avatar :size="36" style="background: linear-gradient(135deg, #409EFF, #337ECC)">🤖</el-avatar>
        <div class="message-bubble ai-bubble loading-bubble">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="qa-input-area">
      <el-input
        v-model="inputText"
        placeholder="输入您的问题... (Enter 发送, Shift+Enter 换行)"
        type="textarea"
        :rows="2"
        :disabled="loading"
        @keydown.enter.exact.prevent="handleSend"
      />
      <div class="input-actions">
        <el-checkbox v-model="useRag" size="small">RAG检索增强</el-checkbox>
        <el-button type="primary" :loading="loading" @click="handleSend" :disabled="!inputText.trim()">
          <el-icon><Promotion /></el-icon> 发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { agentChat, quickReport, clearSession as apiClearSession } from '../api/index.js'
import { marked } from 'marked'

// ---- 状态 ----
const inputText = ref('')
const stockCode = ref('')
const sessionId = ref('session_1')
const loading = ref(false)
const useRag = ref(true)
const messages = ref([])
const chatArea = ref(null)

const suggestions = [
  '分析贵州茅台最近30天的市场情绪',
  '对比最近宁德时代的券商研报观点',
  '提取比亚迪2024年Q1的核心财务数据',
  '生成一份关于AI芯片行业的分析报告',
  '当前市场有哪些投资风险需要注意',
]

// ---- 方法 ----
function scrollToBottom() {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight
    }
  })
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text, { breaks: true })
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  })
}

function handleFeedback(msg, type) {
  msg.feedback = type
  ElMessage.success(`已反馈: ${type}`)
}

async function handleSend() {
  const question = inputText.value.trim()
  if (!question || loading.value) return

  messages.value.push({
    role: 'user',
    content: question,
    timestamp: new Date().toISOString(),
  })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await agentChat({
      question,
      session_id: sessionId.value === 'new' ? `session_${Date.now()}` : sessionId.value,
      stock_code: stockCode.value || undefined,
      use_rag: useRag.value,
    })

    messages.value.push({
      role: 'ai',
      content: res.answer,
      thoughtChain: res.thought_chain || [],
      sources: res.sources || [],
      timestamp: new Date().toISOString(),
    })

    if (sessionId.value === 'new' && res.session_id) {
      sessionId.value = res.session_id
    }
  } catch (e) {
    messages.value.push({
      role: 'ai',
      content: '抱歉，处理您的问题时遇到了错误: ' + (e.message || '未知错误'),
      thoughtChain: [],
      sources: [],
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function handleSuggestion(q) {
  inputText.value = q
  handleSend()
}

async function handleQuickReport() {
  if (!stockCode.value) return
  loading.value = true
  try {
    const res = await quickReport(stockCode.value, '')
    const content = JSON.stringify(res, null, 2)
    messages.value.push({
      role: 'user',
      content: `快捷分析: ${stockCode.value}`,
    })
    messages.value.push({
      role: 'ai',
      content: `## 📊 ${stockCode.value} 综合研报分析\n\n\`\`\`json\n${content}\n\`\`\``,
      thoughtChain: [],
      sources: [{ tool: 'quick_report' }],
    })
  } catch (e) {
    ElMessage.error('快捷分析失败: ' + (e.message || ''))
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function handleClearSession() {
  try {
    await apiClearSession(sessionId.value)
    messages.value = []
    ElMessage.success('会话已清除')
  } catch {
    ElMessage.error('清除失败')
  }
}

// ---- 生命周期 ----
onMounted(() => {
  messages.value.push({
    role: 'ai',
    content: '您好！我是**金融研报智能分析助手**。我可以帮您分析研报、提取数据、对比观点、回答投资问题。请在上方输入您关心的问题，或点击下方推荐问题快速开始 👇',
    thoughtChain: [],
    sources: [],
  })
})
</script>

<style scoped>
.qa-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  max-width: 1000px;
  margin: 0 auto;
}

/* 工具栏 */
.qa-toolbar {
  margin-bottom: 16px;
  flex-shrink: 0;
}

.qa-toolbar :deep(.el-card__body) {
  padding: 12px 16px;
}

.toolbar-tip {
  color: #909399;
  font-size: 12px;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 对话区 */
.qa-chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.qa-welcome {
  text-align: center;
  padding: 40px 20px;
  color: #606266;
}

.welcome-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.qa-welcome h2 {
  font-size: 24px;
  margin-bottom: 8px;
  color: #303133;
}

.qa-welcome p {
  font-size: 14px;
  margin-bottom: 24px;
  color: #909399;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.suggestion-chip {
  cursor: pointer;
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 20px;
  transition: all 0.3s;
}

.suggestion-chip:hover {
  background-color: #409EFF;
  color: #fff;
  border-color: #409EFF;
}

/* 消息气泡 */
.qa-message {
  margin-bottom: 16px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 4px;
}

.user-row {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-bubble {
  max-width: 75%;
  border-radius: 12px;
  padding: 14px 18px;
  position: relative;
}

.user-bubble {
  background: linear-gradient(135deg, #409EFF, #337ECC);
  color: #fff;
}

.ai-bubble {
  background: #ffffff;
  border: 1px solid #e4e7ed;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.bubble-text {
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.loading-bubble {
  padding: 20px 28px;
}

/* 思考链 */
.thought-collapse {
  margin-bottom: 10px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.thought-collapse :deep(.el-collapse-item__header) {
  font-size: 12px;
  color: #909399;
  padding: 6px 12px;
  height: 32px;
  line-height: 32px;
}

.thought-step {
  font-size: 12px;
  color: #606266;
  padding: 4px 0;
  font-family: 'Consolas', 'Menlo', monospace;
}

.thought-action {
  color: #409EFF;
}

.thought-input, .thought-output {
  color: #909399;
  padding-left: 16px;
  word-break: break-all;
}

.thought-finish {
  color: #67C23A;
}

/* 来源标签 */
.source-tags {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.source-label {
  font-size: 12px;
  color: #909399;
}

.source-tag {
  font-size: 11px;
}

/* 消息操作 */
.message-actions {
  margin-top: 8px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-bubble:hover .message-actions {
  opacity: 1;
}

/* Markdown 样式 */
.markdown-body :deep(h1), .markdown-body :deep(h2), .markdown-body :deep(h3) {
  margin: 12px 0 8px;
  font-weight: 600;
}

.markdown-body :deep(p) { margin: 6px 0; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { padding-left: 20px; }
.markdown-body :deep(code) { background: #f5f7fa; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.markdown-body :deep(pre) { background: #1d1e2c; color: #e5e5e5; padding: 12px; border-radius: 8px; overflow-x: auto; }
.markdown-body :deep(blockquote) { border-left: 3px solid #409EFF; padding-left: 12px; color: #606266; margin: 8px 0; }

/* 输入区 */
.qa-input-area {
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-top: 12px;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.05);
  border: 1px solid #e4e7ed;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

/* 输入动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409EFF;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-10px); opacity: 1; }
}
</style>

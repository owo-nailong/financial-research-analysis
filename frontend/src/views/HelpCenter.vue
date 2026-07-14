<template>
  <div class="help-page">
    <aside class="help-nav">
      <button
        v-for="s in sections"
        :key="s.id"
        type="button"
        class="nav-btn"
        :class="{ active: active === s.id }"
        @click="active = s.id"
      >
        {{ s.title }}
      </button>
    </aside>

    <section class="help-body">
      <template v-if="active === 'guide'">
        <h2>新手引导</h2>
        <p class="lead">欢迎使用智研AI金融研报智能分析与投资决策辅助系统。按下列顺序即可完成首日上手。</p>
        <ol class="steps">
          <li>
            <strong>登录</strong>：管理员可管理知识库与同步行情；普通用户可对话、看看板、生成内容。
          </li>
          <li>
            <strong>智能对话</strong>：在输入框用自然语言提问，例如「分析贵州茅台近期市场情绪」。可填写「关注标的代码」（如 600519）缩小工具检索范围；勾选「启用知识库检索」后会引用已入库文档。
          </li>
          <li>
            <strong>数据看板</strong>：输入股票代码，查看日K蜡烛图、周期最高/最低与均线。管理员可点击「同步真实数据入库」从东方财富/巨潮抓取研报、新闻、公告。
          </li>
          <li>
            <strong>内容工作台</strong>：选择模板生成研报摘要或投资建议，可复制、下载 Markdown；管理员可将结果存入知识库参与 RAG。
          </li>
          <li>
            <strong>多智能体协调</strong>：对复杂问题启用多角色（分析师、投资者视角、审核、经理综合）协作生成更稳健的答复。
          </li>
          <li>
            <strong>知识库与 RAG（管理员）</strong>：在知识库管理中导入文档、开关启用状态；在 RAG 参数中调节 TopK、分块与阈值。
          </li>
        </ol>
        <div class="callout">
          <strong>小提示</strong>：本地模型（Ollama）生成答案可能需要 20–60 秒，请耐心等待转圈结束。
        </div>
      </template>

      <template v-else-if="active === 'faq'">
        <h2>常见问题解答</h2>
        <div v-for="(item, i) in faq" :key="i" class="faq-item">
          <h3>Q{{ i + 1 }}. {{ item.q }}</h3>
          <p>{{ item.a }}</p>
        </div>
      </template>

      <template v-else-if="active === 'disclaimer'">
        <h2>免责声明</h2>
        <div class="prose">
          <p>
            本系统提供的全部内容，包括但不限于智能对话回答、研报摘要、评级汇总、市场情绪指数、K线图表、多智能体报告等，
            <strong>仅供学习、研究与信息辅助参考</strong>，不构成任何证券、期货或其他金融产品的投资建议、要约或承诺。
          </p>
          <p>
            金融市场存在固有风险，历史数据与模型输出不代表未来表现。用户应独立判断，并根据自身风险承受能力审慎决策；
            因使用或依赖本系统信息而产生的任何直接或间接损失，开发者与运营方不承担责任。
          </p>
          <p>
            数据来源于公开互联网接口（如东方财富、巨潮资讯等）及用户自行导入的文档，系统不保证数据的完整性、及时性与准确性。
            第三方网站的展示样式与版权归原权利人所有，本系统仅在合规范围内做聚合与可视化。
          </p>
          <p>
            使用本系统即表示您已阅读并同意本免责声明。如不同意，请立即停止使用。
          </p>
          <p class="muted">最后更新：2026-07-14</p>
        </div>
      </template>

      <template v-else-if="active === 'feedback'">
        <h2>用户反馈</h2>
        <p class="lead">欢迎反馈使用中的问题、体验建议或数据异常。管理员可在系统日志中查看汇总。</p>
        <form class="fb-form" @submit.prevent="submit">
          <label>
            反馈类型
            <select v-model="form.category">
              <option value="bug">功能异常</option>
              <option value="ux">体验建议</option>
              <option value="data">数据/图表问题</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            联系方式（可选）
            <input v-model="form.contact" placeholder="邮箱或手机号" />
          </label>
          <label>
            反馈内容
            <textarea v-model="form.content" rows="6" required placeholder="请描述现象、复现步骤或建议..." />
          </label>
          <button type="submit" class="btn primary" :disabled="sending || !form.content.trim()">
            {{ sending ? '提交中...' : '提交反馈' }}
          </button>
          <p v-if="msg" class="msg">{{ msg }}</p>
        </form>
      </template>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { submitFeedback } from '../api'

const active = ref('guide')
const sending = ref(false)
const msg = ref('')
const form = reactive({
  category: 'ux',
  contact: '',
  content: '',
})

const sections = [
  { id: 'guide', title: '新手引导' },
  { id: 'faq', title: '常见问题' },
  { id: 'disclaimer', title: '免责声明' },
  { id: 'feedback', title: '用户反馈' },
]

const faq = [
  {
    q: '关注标的代码是什么？',
    a: '指 A 股六位证券代码，例如 600519 代表贵州茅台、300750 代表宁德时代。填写后，快捷分析与工具会优先检索该股票相关研报、公告与情绪；不填也可直接用自然语言提问。',
  },
  {
    q: '为什么回答比较慢？',
    a: '系统默认调用本机 Ollama 大模型（如 qwen2.5）。单次生成常需数十秒；多智能体模式会连续调用多次模型，耗时更长，属正常现象。',
  },
  {
    q: 'K 线图数据从哪里来？',
    a: '日 K 来自东方财富公开 K 线接口（push2his.eastmoney.com），展示为蜡烛图（开高低收）与均线，涨红跌绿符合 A 股习惯。',
  },
  {
    q: '普通用户和管理员权限有何区别？',
    a: '普通用户：对话、看板、内容工作台、帮助中心、多智能体，并可修改自己的密码。管理员额外：知识库管理、RAG 参数、真实数据同步、系统用户管理与重置他人密码。',
  },
  {
    q: '知识库文档如何参与回答？',
    a: '启用「知识库检索」后，系统会按向量相似度检索已启用文档片段，再交给模型组织回答。仅管理员可导入、启停文档。',
  },
  {
    q: '多智能体协调做什么？',
    a: '依次调用「资深金融分析师 → 普通投资者视角 → 审核员 → 经理综合」四个角色，降低单次回答片面性，适合复杂投资相关问题。',
  },
]

async function submit() {
  sending.value = true
  msg.value = ''
  try {
    await submitFeedback({
      category: form.category,
      contact: form.contact,
      content: form.content.trim(),
    })
    msg.value = '感谢反馈，我们已记录。'
    form.content = ''
  } catch (e) {
    msg.value = '提交失败：' + (e.message || e)
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.help-page {
  height: 100%;
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0;
  overflow: hidden;
}

.help-nav {
  border-right: 1px solid var(--border);
  background: #fafafa;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-btn {
  text-align: left;
  border: none;
  background: transparent;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text);
}

.nav-btn:hover {
  background: #f0f0f0;
}

.nav-btn.active {
  background: #111;
  color: #fff;
  font-weight: 600;
}

.help-body {
  overflow: auto;
  padding: 28px 32px 40px;
  max-width: 820px;
}

h2 {
  font-size: 22px;
  margin-bottom: 12px;
}

h3 {
  font-size: 15px;
  margin: 16px 0 6px;
}

.lead {
  color: var(--text-secondary);
  line-height: 1.65;
  margin-bottom: 18px;
}

.steps {
  padding-left: 1.25em;
  line-height: 1.75;
  color: var(--text);
}

.steps li {
  margin-bottom: 10px;
}

.callout {
  margin-top: 20px;
  padding: 14px 16px;
  background: #f7f7f8;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.faq-item {
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
  margin-bottom: 8px;
}

.faq-item p {
  color: var(--text-secondary);
  line-height: 1.65;
  font-size: 14px;
}

.prose p {
  line-height: 1.75;
  margin-bottom: 14px;
  color: var(--text);
}

.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.fb-form label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}

.fb-form input,
.fb-form select,
.fb-form textarea {
  display: block;
  width: 100%;
  margin-top: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
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

.msg {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

@media (max-width: 800px) {
  .help-page {
    grid-template-columns: 1fr;
  }
  .help-nav {
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>

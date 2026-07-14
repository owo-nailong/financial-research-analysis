<template>
  <div class="dash-page">
    <div class="toolbar">
      <div class="field search-field">
        <label>股票代码或名称</label>
        <input
          v-model="query"
          placeholder="代码或名称，如 600519 / 茅台"
          maxlength="32"
          @input="onQueryInput"
          @keydown.enter.prevent="reload"
          @focus="showSuggest = suggestions.length > 0"
          @blur="onBlurSuggest"
        />
        <ul v-if="showSuggest && suggestions.length" class="suggest">
          <li
            v-for="s in suggestions"
            :key="s.code"
            @mousedown.prevent="pickSuggest(s)"
          >
            <strong>{{ s.name || '—' }}</strong>
            <span class="code">{{ s.code }}</span>
          </li>
        </ul>
      </div>
      <div class="field">
        <label>周期</label>
        <select v-model.number="limit">
          <option :value="60">近60天</option>
          <option :value="90">近90天</option>
          <option :value="120">近120天</option>
          <option :value="180">近180天</option>
        </select>
      </div>
      <button type="button" class="btn primary" :disabled="loading" @click="reload">搜索</button>
      <button v-if="isAdmin" type="button" class="btn" :disabled="syncing" @click="syncLive">
        {{ syncing ? '同步中...' : '同步真实数据入库' }}
      </button>
      <span class="tag">东方财富日K · 蜡烛图</span>
    </div>

    <div v-if="msg" class="msg">{{ msg }}</div>

    <div class="header-row">
      <div>
        <h2 class="title">{{ stockName || '—' }} <span class="code">({{ stockCode }})</span></h2>
      </div>
      <div class="price-block" :class="changePct >= 0 ? 'up' : 'down'">
        <div class="price">¥{{ latestClose != null ? Number(latestClose).toFixed(2) : '—' }}</div>
        <div class="chg">
          {{ changePct == null ? '—' : (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%' }}
        </div>
      </div>
    </div>

    <div class="cards">
      <div class="card">
        <div class="k">周期最高</div>
        <div class="v up">¥{{ periodHigh != null ? Number(periodHigh).toFixed(2) : '—' }}</div>
      </div>
      <div class="card">
        <div class="k">周期最低</div>
        <div class="v down">¥{{ periodLow != null ? Number(periodLow).toFixed(2) : '—' }}</div>
      </div>
      <div class="card">
        <div class="k">5日均价</div>
        <div class="v">¥{{ ma5 != null ? Number(ma5).toFixed(2) : '—' }}</div>
      </div>
      <div class="card">
        <div class="k">20日均价</div>
        <div class="v">¥{{ ma20 != null ? Number(ma20).toFixed(2) : '—' }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h3>K线图 — {{ stockName || stockCode }}</h3>
        <a class="src" :href="sourceUrl" target="_blank" rel="noreferrer">数据源</a>
      </div>
      <div v-if="loading" class="empty">加载中...</div>
      <div v-else-if="!points.length" class="empty">暂无 K 线数据</div>
      <div v-else class="chart-wrap">
        <svg class="chart" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none">
          <!-- grid + y labels -->
          <g v-for="(gy, i) in yTicks" :key="'yt'+i">
            <line :x1="PAD_L" :y1="gy.y" :x2="W - PAD_R" :y2="gy.y" stroke="#f0f0f0" />
            <text :x="4" :y="gy.y + 4" font-size="11" fill="#9aa0a6">{{ gy.label }}</text>
          </g>
          <!-- candles -->
          <g v-for="(c, i) in candles" :key="'c'+i">
            <line
              :x1="c.cx"
              :y1="c.yHigh"
              :x2="c.cx"
              :y2="c.yLow"
              :stroke="c.color"
              stroke-width="1"
            />
            <rect
              :x="c.x"
              :y="c.yBody"
              :width="c.bw"
              :height="Math.max(c.bh, 1)"
              :fill="c.color"
              :stroke="c.color"
            />
          </g>
          <!-- MA5 -->
          <polyline
            v-if="ma5Line"
            fill="none"
            stroke="#f9a825"
            stroke-width="1.5"
            :points="ma5Line"
          />
          <!-- MA20 -->
          <polyline
            v-if="ma20Line"
            fill="none"
            stroke="#5c6bc0"
            stroke-width="1.5"
            :points="ma20Line"
          />
          <!-- x axis -->
          <line :x1="PAD_L" :y1="PLOT_B" :x2="W - PAD_R" :y2="PLOT_B" stroke="#e8e8e8" />
          <text
            v-for="(xt, i) in xTicks"
            :key="'xt'+i"
            :x="xt.x"
            :y="H - 8"
            font-size="10"
            fill="#9aa0a6"
            text-anchor="middle"
          >{{ xt.label }}</text>
        </svg>
        <div class="legend">
          <span><i class="sw up" />阳线</span>
          <span><i class="sw down" />阴线</span>
          <span><i class="ln ma5" />MA5</span>
          <span><i class="ln ma20" />MA20</span>
          <span class="muted">纵轴按最高~最低自动缩放，避免曲线被压扁</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { dashboardKline, dashboardStockSearch, dashboardSync } from '../api'

const user = JSON.parse(localStorage.getItem('user') || '{}')
const isAdmin = user.role === 'admin'
const query = ref('600519')
const stockCode = ref('600519')
const stockName = ref('')
const points = ref([])
const limit = ref(120)
const sourceUrl = ref('https://push2his.eastmoney.com/api/qt/stock/kline/get')
const loading = ref(false)
const syncing = ref(false)
const msg = ref('')
const suggestions = ref([])
const showSuggest = ref(false)
let searchTimer = null

function onQueryInput() {
  clearTimeout(searchTimer)
  const q = query.value.trim()
  if (!q) {
    suggestions.value = []
    showSuggest.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const res = await dashboardStockSearch(q, 8)
      suggestions.value = res.data || []
      showSuggest.value = suggestions.value.length > 0
    } catch (_) {
      suggestions.value = []
      showSuggest.value = false
    }
  }, 280)
}

function pickSuggest(s) {
  query.value = `${s.name || ''} ${s.code}`.trim()
  stockCode.value = s.code
  stockName.value = s.name || ''
  showSuggest.value = false
  suggestions.value = []
  reload()
}

function onBlurSuggest() {
  setTimeout(() => {
    showSuggest.value = false
  }, 150)
}

const W = 900
const H = 360
const PAD_L = 52
const PAD_R = 16
const PAD_T = 16
const PAD_B = 28
const PLOT_T = PAD_T
const PLOT_B = H - PAD_B

function ma(closes, w) {
  const out = []
  for (let i = 0; i < closes.length; i++) {
    if (i + 1 < w) out.push(null)
    else {
      let s = 0
      for (let j = i + 1 - w; j <= i; j++) s += closes[j]
      out.push(s / w)
    }
  }
  return out
}

const closes = computed(() => points.value.map((p) => p.close))
const latestClose = computed(() => (closes.value.length ? closes.value[closes.value.length - 1] : null))
const changePct = computed(() => {
  if (closes.value.length < 2) return null
  const a = closes.value[0]
  const b = closes.value[closes.value.length - 1]
  return a ? ((b - a) / a) * 100 : null
})
const periodHigh = computed(() => {
  if (!points.value.length) return null
  return Math.max(...points.value.map((p) => p.high ?? p.close))
})
const periodLow = computed(() => {
  if (!points.value.length) return null
  return Math.min(...points.value.map((p) => p.low ?? p.close))
})
const ma5Series = computed(() => ma(closes.value, 5))
const ma20Series = computed(() => ma(closes.value, 20))
const ma5 = computed(() => {
  const s = ma5Series.value
  return s.length ? s[s.length - 1] : null
})
const ma20 = computed(() => {
  const s = ma20Series.value
  return s.length ? s[s.length - 1] : null
})

const scale = computed(() => {
  const pts = points.value
  if (!pts.length) return { min: 0, max: 1, y: () => 0, x: () => 0, slot: 1 }
  const highs = pts.map((p) => p.high ?? p.close)
  const lows = pts.map((p) => p.low ?? p.close)
  let min = Math.min(...lows)
  let max = Math.max(...highs)
  // pad 3% so candles aren't flat against edges
  const pad = (max - min) * 0.04 || max * 0.01 || 1
  min -= pad
  max += pad
  const span = max - min || 1
  const n = pts.length
  const plotW = W - PAD_L - PAD_R
  const slot = plotW / Math.max(n, 1)
  return {
    min,
    max,
    slot,
    y: (v) => PLOT_T + ((max - v) / span) * (PLOT_B - PLOT_T),
    x: (i) => PAD_L + i * slot + slot / 2,
  }
})

const candles = computed(() => {
  const pts = points.value
  const sc = scale.value
  const bw = Math.max(sc.slot * 0.55, 1.5)
  return pts.map((p, i) => {
    const o = p.open
    const c = p.close
    const h = p.high ?? Math.max(o, c)
    const l = p.low ?? Math.min(o, c)
    const up = c >= o
    const yO = sc.y(o)
    const yC = sc.y(c)
    const yBody = Math.min(yO, yC)
    const bh = Math.max(Math.abs(yO - yC), 1)
    return {
      cx: sc.x(i),
      x: sc.x(i) - bw / 2,
      yHigh: sc.y(h),
      yLow: sc.y(l),
      yBody,
      bh,
      bw,
      color: up ? '#ef5350' : '#26a69a',
    }
  })
})

const ma5Line = computed(() => {
  const s = ma5Series.value
  const sc = scale.value
  return s
    .map((v, i) => (v == null ? null : `${sc.x(i)},${sc.y(v)}`))
    .filter(Boolean)
    .join(' ')
})
const ma20Line = computed(() => {
  const s = ma20Series.value
  const sc = scale.value
  return s
    .map((v, i) => (v == null ? null : `${sc.x(i)},${sc.y(v)}`))
    .filter(Boolean)
    .join(' ')
})

const yTicks = computed(() => {
  const sc = scale.value
  const n = 5
  const ticks = []
  for (let i = 0; i <= n; i++) {
    const v = sc.max - ((sc.max - sc.min) * i) / n
    ticks.push({ y: sc.y(v), label: v.toFixed(0) })
  }
  return ticks
})

const xTicks = computed(() => {
  const pts = points.value
  if (!pts.length) return []
  const sc = scale.value
  const idxs = [0, Math.floor(pts.length / 3), Math.floor((pts.length * 2) / 3), pts.length - 1]
  return [...new Set(idxs)].map((i) => ({
    x: sc.x(i),
    label: (pts[i].date || '').slice(5),
  }))
})

async function reload() {
  loading.value = true
  msg.value = ''
  showSuggest.value = false
  try {
    const q = query.value.trim() || stockCode.value.trim() || '600519'
    const res = await dashboardKline(q, limit.value)
    if (res.status !== 'ok') {
      msg.value = res.message || 'K线获取失败'
      points.value = []
      stockName.value = ''
      return
    }
    points.value = (res.data || []).map((p) => ({
      ...p,
      open: Number(p.open),
      close: Number(p.close),
      high: Number(p.high ?? p.close),
      low: Number(p.low ?? p.close),
      volume: Number(p.volume || 0),
    }))
    stockCode.value = res.stock_code || stockCode.value
    stockName.value = res.stock_name || stockName.value || ''
    if (stockName.value && stockCode.value) {
      query.value = `${stockName.value} ${stockCode.value}`
    } else if (stockCode.value) {
      query.value = stockCode.value
    }
    sourceUrl.value = res.source_url || sourceUrl.value
    if (!stockName.value) {
      msg.value = '已加载行情，但未解析到股票名称（可尝试输入完整代码或中文名）'
    }
  } catch (e) {
    msg.value = e.message
    points.value = []
  } finally {
    loading.value = false
  }
}

async function syncLive() {
  syncing.value = true
  msg.value = ''
  try {
    const code = stockCode.value.trim() || '600519'
    const res = await dashboardSync(code)
    msg.value = `同步完成：研报 ${res.reports?.total || 0} / 新闻 ${res.news?.total || 0} / 公告 ${res.announcements?.total || 0}`
    await reload()
  } catch (e) {
    msg.value = e.message
  } finally {
    syncing.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.dash-page {
  height: 100%;
  overflow: auto;
  padding: 20px 24px 32px;
  background: #f7f8fa;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
}

.field label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.field input,
.field select {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  min-width: 120px;
  background: #fff;
}

.search-field {
  position: relative;
}

.search-field input {
  min-width: 220px;
}

.suggest {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 4px);
  z-index: 20;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  max-height: 240px;
  overflow: auto;
}

.suggest li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}

.suggest li:hover {
  background: #f5f5f5;
}

.suggest .code {
  color: var(--text-muted);
  font-family: ui-monospace, Consolas, monospace;
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
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tag {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

.msg {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
}

.title {
  font-size: 20px;
  font-weight: 700;
}

.code {
  font-weight: 400;
  color: var(--text-muted);
  font-size: 15px;
}

.price-block {
  text-align: right;
}

.price {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.chg {
  font-size: 14px;
  margin-top: 4px;
}

.up {
  color: #ef5350;
}

.down {
  color: #26a69a;
}

.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
}

.card .k {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.card .v {
  font-size: 18px;
  font-weight: 600;
  color: #222;
}

.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.panel-head h3 {
  margin: 0;
  font-size: 15px;
}

.src {
  font-size: 12px;
  color: var(--text-secondary);
}

.chart-wrap {
  width: 100%;
}

.chart {
  width: 100%;
  height: 380px;
  display: block;
  background: #fff;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
  align-items: center;
}

.legend .sw {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 4px;
  vertical-align: middle;
}

.legend .sw.up {
  background: #ef5350;
}

.legend .sw.down {
  background: #26a69a;
}

.legend .ln {
  display: inline-block;
  width: 14px;
  height: 2px;
  margin-right: 4px;
  vertical-align: middle;
}

.legend .ln.ma5 {
  background: #f9a825;
}

.legend .ln.ma20 {
  background: #5c6bc0;
}

.legend .muted {
  color: var(--text-muted);
}

.empty {
  padding: 48px;
  text-align: center;
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .cards {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

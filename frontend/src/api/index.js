/**
 * API client for FastAPI backend with JWT auth.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 180000,
  headers: { 'Content-Type': 'application/json' },
})

// Avoid system proxy hijacking local /api (common cause of "local site always drops")
try {
  if (typeof window !== 'undefined') {
    // axios browser uses XHR; proxy is mainly a Node issue, but keep explicit base
  }
} catch (_) {
  /* ignore */
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (!window.location.hash.includes('/login')) {
        window.location.hash = '#/login'
      }
    }
    const msg = error.response?.data?.detail || error.response?.data?.message || error.message || 'request failed'
    return Promise.reject(new Error(typeof msg === 'string' ? msg : JSON.stringify(msg)))
  }
)

export const login = (username, password) => api.post('/auth/login', { username, password })
export const me = () => api.get('/auth/me')
export const listUsers = () => api.get('/auth/users')
export const createUser = (payload) => api.post('/auth/users', payload)

export const healthCheck = () => api.get('/health')
export const listTools = () => api.get('/tools')
export const dashboardSummary = () => api.get('/dashboard/summary')
export const dashboardKline = (stockCode = '600519', limit = 90) =>
  api.get('/dashboard/kline', { params: { stock_code: stockCode, limit } })
export const dashboardSync = (stockCode = '600519') =>
  api.post(`/dashboard/sync?stock_code=${encodeURIComponent(stockCode)}`)
export const dataSources = () => api.get('/data/sources')

export const submitFeedback = (payload) => api.post('/feedback', payload)
export const multiAgentRun = (payload) => api.post('/agent/multi', payload, { timeout: 600000 })
export const ingestReferences = (paths) => api.post('/admin/ingest-references', { paths })

export const fetchReports = (params) => api.post('/fetch/reports', params)
export const fetchNews = (params) => api.post('/fetch/news', params)
export const fetchAnnouncements = (params) => api.post('/fetch/announcements', params)
export const fetchSocial = (params) => api.post('/fetch/social', params)

export const extractFinancial = (params) => api.post('/extract/financial', params)
export const extractForecast = (params) => api.post('/extract/forecast', params)
export const extractRatings = (params) => api.post('/extract/ratings', params)
export const extractRisks = (params) => api.post('/extract/risks', params)

export const compareOpinions = (params) => api.post('/analysis/compare', params)
export const analyzeSentiment = (params) => api.post('/analysis/sentiment', params)
export const marketSentiment = (params) => api.post('/analysis/market-sentiment', params)

export const generateSummary = (params) => api.post('/generate/summary', params)
export const generateContent = (params) => api.post('/generate/content', params)
export const batchPortfolio = (params) => api.post('/generate/portfolio', params)
export const investmentQA = (params) => api.post('/qa/investment', params)
export const searchKB = (params) => api.post('/kb/search', params)

export const agentChat = (params) => api.post('/agent/chat', params)
export const quickReport = (stockCode, stockName = '') =>
  api.post(`/agent/quick-report?stock_code=${encodeURIComponent(stockCode)}&stock_name=${encodeURIComponent(stockName)}`)
export const getSessionHistory = (sessionId) => api.get(`/agent/sessions/${sessionId}`)
export const clearSession = (sessionId) => api.delete(`/agent/sessions/${sessionId}`)

export const kbAdd = (params) => api.post('/kb/add', params)
export const kbGet = (docId) => api.get(`/kb/${docId}`)
export const kbDelete = (docId) => api.delete(`/kb/${docId}`)
export const kbToggle = (docId, enabled) =>
  api.patch(`/kb/${docId}/toggle?enabled=${enabled ? 'true' : 'false'}`)
export const kbList = (params) => api.get('/kb/list', { params })
export const kbStatus = () => api.get('/kb/status')

export const kbImport = (formData) =>
  api.post('/kb/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  })

export const getRagParams = () => api.get('/rag/params')
export const updateRagParams = (params) => api.put('/rag/params', params)

export const templateCreate = (params) => api.post('/templates/create', params)
export const templateList = (category) => api.get('/templates/list', { params: { category } })
export const templateUpdate = (id, params) => api.put(`/templates/${id}`, params)

export default api

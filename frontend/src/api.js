const base = (import.meta.env.VITE_API_URL || 'http://localhost:5000/api').replace(/\/$/, '')

let csrfToken = ''

function query(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

async function request(path, options = {}) {
  const method = options.method || 'GET'
  const headers = { ...(options.headers || {}) }
  const hasJsonBody = options.body !== undefined && !(options.body instanceof FormData)
  if (hasJsonBody) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && csrfToken) headers['X-CSRF-Token'] = csrfToken

  let response
  try {
    response = await fetch(`${base}${path}`, {
      credentials: 'include',
      ...options,
      headers,
    })
  } catch {
    throw new Error('Cannot reach the Clearpath server. Is the backend running on port 5000?')
  }

  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await response.json() : await response.blob()

  if (!response.ok) {
    const message = isJson ? payload.error || `Request failed (${response.status})` : `Request failed (${response.status})`
    const error = new Error(message)
    error.status = response.status
    error.code = isJson ? payload.code : undefined
    error.payload = payload
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new CustomEvent('clearpath:unauthorized'))
    }
    throw error
  }

  if (isJson && payload?.csrf_token) csrfToken = payload.csrf_token
  return payload
}

const get = (path) => request(path)
const post = (path, data) => request(path, { method: 'POST', body: JSON.stringify(data || {}) })
const patch = (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data || {}) })
const del = (path) => request(path, { method: 'DELETE' })

export const api = {
  // Authentication and account
  me: () => get('/auth/me'),
  login: (data) => post('/auth/login', data),
  register: (data) => post('/auth/register', data),
  demoLogin: () => post('/auth/demo', {}),
  logout: () => post('/auth/logout', {}),
  updateProfile: (data) => patch('/profile', data),
  changePassword: (data) => post('/profile/password', data),
  exportAccount: () => get('/account/export'),
  deleteAccount: (password) => request('/account', { method: 'DELETE', body: JSON.stringify({ password }) }),

  // Dashboard and insights
  overview: (month) => get(`/insights/overview${query({ month })}`),
  health: () => get('/insights/health'),
  forecast: (horizon = 3) => get(`/insights/forecast${query({ horizon })}`),
  cashflow: (months = 12) => get(`/insights/cashflow${query({ months })}`),
  trends: (months = 6) => get(`/insights/trends${query({ months })}`),
  recurring: () => get('/insights/recurring'),
  anomalies: () => get('/insights/anomalies'),
  netWorth: () => get('/insights/net-worth'),
  safeToSpend: () => get('/insights/safe-to-spend'),
  affordability: (data) => post('/insights/affordability', data),
  whatIf: (data) => post('/insights/what-if', data),
  researchSummary: () => get('/insights/research-summary'),

  // Transactions
  transactions: (params = {}) => get(`/transactions${query(params)}`),
  saveTransaction: (data, id) => (id ? patch(`/transactions/${id}`, data) : post('/transactions', data)),
  deleteTransaction: (id) => del(`/transactions/${id}`),
  suggestCategory: (data) => post('/transactions/suggest-category', data),
  importTransactions: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/transactions/import', { method: 'POST', body: form })
  },
  exportTransactions: () => get('/transactions/export'),

  // Budgets
  budgets: (month) => get(`/budgets${query({ month })}`),
  createBudget: (data) => post('/budgets', data),
  updateBudget: (id, data) => patch(`/budgets/${id}`, data),
  deleteBudget: (id) => del(`/budgets/${id}`),
  copyBudgets: (data) => post('/budgets/copy', data),

  // Goals
  goals: () => get('/goals'),
  goal: (id) => get(`/goals/${id}`),
  createGoal: (data) => post('/goals', data),
  updateGoal: (id, data) => patch(`/goals/${id}`, data),
  deleteGoal: (id) => del(`/goals/${id}`),
  addContribution: (id, data) => post(`/goals/${id}/contributions`, data),
  deleteContribution: (goalId, contributionId) => del(`/goals/${goalId}/contributions/${contributionId}`),

  // Debt
  debts: (extra = 0) => get(`/debts${query({ extra })}`),
  debtPlan: (extra = 0) => get(`/debts/plan${query({ extra })}`),
  createDebt: (data) => post('/debts', data),
  updateDebt: (id, data) => patch(`/debts/${id}`, data),
  deleteDebt: (id) => del(`/debts/${id}`),

  // Assets
  assets: () => get('/assets'),
  createAsset: (data) => post('/assets', data),
  updateAsset: (id, data) => patch(`/assets/${id}`, data),
  deleteAsset: (id) => del(`/assets/${id}`),

  // Nudges and gamification
  nudges: () => get('/nudges'),
  respondNudge: (id, action) => post(`/nudges/${id}/respond`, { action }),
  nudgeEffectiveness: () => get('/nudges/effectiveness'),
  gamification: () => get('/gamification'),

  // Advisor
  advisorStatus: () => get('/advisor/status'),
  advisorTools: () => get('/advisor/tools'),
  advisorSessions: () => get('/advisor/sessions'),
  advisorSession: (id) => get(`/advisor/sessions/${id}`),
  createAdvisorSession: (data) => post('/advisor/sessions', data),
  deleteAdvisorSession: (id) => del(`/advisor/sessions/${id}`),
  chat: (data) => post('/advisor/chat', data),
  messageFeedback: (id, data) => post(`/advisor/messages/${id}/feedback`, data),

  // Literacy
  literacyModules: () => get('/literacy/modules'),
  literacyModule: (slug) => get(`/literacy/modules/${slug}`),
  submitQuiz: (slug, answers) => post(`/literacy/modules/${slug}/quiz`, { answers }),
  literacyProgress: () => get('/literacy/progress'),
  searchKnowledge: (q) => get(`/literacy/search${query({ q })}`),

  // Calculators
  emi: (data) => post('/calculators/emi', data),
  sip: (data) => post('/calculators/sip', data),
  swp: (data) => post('/calculators/swp', data),
  fire: (data) => post('/calculators/fire', data),
  compound: (data) => post('/calculators/compound', data),
}

export { base }

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, BellRing, Info, ShieldAlert, X } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'
import { Spinner } from './UI'

const ACTION_ROUTES = {
  open_budgets: '/budgets',
  open_goals: '/goals',
  open_insights: '/insights',
  open_transactions: '/transactions',
}

const SEVERITY_ICON = {
  critical: ShieldAlert,
  attention: BellRing,
  info: Info,
}

export default function NudgeCard({ nudge, onChanged, compact = false }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [busy, setBusy] = useState('')
  const Icon = SEVERITY_ICON[nudge.severity] || Info

  async function respond(action, follow = false) {
    setBusy(action)
    try {
      await api.respondNudge(nudge.id, action)
      if (action === 'dismiss') toast.push('Nudge dismissed. It will not return this month.', 'info')
      if (action === 'accept') toast.push('Marked as acted on. Five points added.', 'success')
      onChanged?.()
      if (follow) navigate(ACTION_ROUTES[nudge.action_type] || '/insights')
    } catch (error) {
      toast.push(error.message, 'error')
    } finally {
      setBusy('')
    }
  }

  return (
    <article className={`nudge nudge-${nudge.severity} ${compact ? 'nudge-compact' : ''}`}>
      <div className="nudge-head">
        <span className="nudge-icon">
          <Icon size={17} />
        </span>
        <div>
          <span className="nudge-kicker">{nudge.severity === 'critical' ? 'Act now' : nudge.severity === 'attention' ? 'Worth a look' : 'Just in time'}</span>
          <h3>{nudge.title}</h3>
        </div>
        <button type="button" className="icon-btn subtle" onClick={() => respond('dismiss')} disabled={Boolean(busy)} aria-label="Dismiss nudge">
          {busy === 'dismiss' ? <Spinner /> : <X size={16} />}
        </button>
      </div>
      <p className="nudge-body">{nudge.body}</p>
      <div className="nudge-actions">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => respond('accept')} disabled={Boolean(busy)}>
          {busy === 'accept' ? 'Saving…' : 'Got it'}
        </button>
        <button type="button" className="btn btn-dark btn-sm" onClick={() => respond('accept', true)} disabled={Boolean(busy)}>
          {nudge.action_label} <ArrowRight size={14} />
        </button>
        <span className="nudge-points">+{nudge.points} pts</span>
      </div>
    </article>
  )
}

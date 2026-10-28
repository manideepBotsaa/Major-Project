import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  Flag,
  Pencil,
  Plus,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { GOAL_STATUS_LABELS } from '../lib/constants'
import { formatDate, formatMoney, formatPct, titleCase, todayISO } from '../lib/format'
import {
  Badge,
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  ProgressBar,
  SectionTitle,
  Spinner,
  StatCard,
  Verdict,
  statusTone,
} from '../components/UI'

const GOAL_CATEGORIES = ['Emergency fund', 'Travel', 'Home', 'Vehicle', 'Education', 'Retirement', 'Wedding', 'General']

function emptyGoal() {
  return {
    name: '',
    category: 'General',
    target_amount: '',
    initial_amount: '',
    monthly_contribution: '',
    target_date: '',
    expected_return: 8,
    priority: 2,
    notes: '',
  }
}

export default function Goals() {
  const { user } = useAuth()
  const toast = useToast()
  const currency = user?.currency || 'INR'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [detailId, setDetailId] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api.goals())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function remove(goal) {
    if (!window.confirm(`Delete “${goal.name}”? Contributions recorded against it will also be removed.`)) return
    try {
      await api.deleteGoal(goal.id)
      toast.push('Goal deleted.')
      await load()
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  const goals = data?.goals || []
  const achieved = goals.filter((goal) => goal.status === 'achieved').length
  const needsAttention = goals.filter((goal) => ['at_risk', 'off_track', 'overdue'].includes(goal.status)).length

  return (
    <>
      <PageHeader
        eyebrow="MAKE THE FUTURE SPECIFIC"
        title="Goals"
        description="A goal turns a vague intention into a monthly number. The Monte Carlo estimate shows the range, not a promise."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setFormOpen(true) }}>
            <Plus size={16} /> New goal
          </button>
        }
      />

      {loading ? (
        <div className="centered-loader"><Spinner label="Loading your goals…" /></div>
      ) : error ? (
        <Card><EmptyState icon={Target} title="Could not load goals">{error}</EmptyState></Card>
      ) : goals.length === 0 ? (
        <Card>
          <EmptyState
            icon={Target}
            title="No goals yet"
            action={<button type="button" className="btn btn-primary btn-sm" onClick={() => setFormOpen(true)}><Plus size={15} /> Create your first goal</button>}
          >
            Start with one goal you can fund this month. An emergency buffer is usually the highest-return first goal.
          </EmptyState>
        </Card>
      ) : (
        <>
          <div className="stat-grid four">
            <StatCard label="Total target" value={formatMoney(data.total_target, currency)} icon={Flag} note={`${data.count} active goals`} />
            <StatCard label="Already saved" value={formatMoney(data.total_saved, currency)} icon={Wallet} note={`${formatPct(data.overall_progress, 1)} of the combined target`} tone="sand" />
            <StatCard label="Monthly commitment" value={formatMoney(data.monthly_committed, currency)} icon={CalendarDays} note="Recurring contributions across goals" tone="blue" />
            <StatCard
              label="Estimated success"
              value={data.average_probability == null ? '—' : formatPct(data.average_probability * 100, 0)}
              icon={TrendingUp}
              note={`${data.on_track_count} on track · ${needsAttention} need attention`}
              tone={needsAttention ? 'clay' : 'green'}
            />
          </div>

          <div className="goal-board">
            {goals.map((goal) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                currency={currency}
                onEdit={() => { setEditing(goal); setFormOpen(true) }}
                onDelete={() => remove(goal)}
                onOpen={() => setDetailId(goal.id)}
              />
            ))}
          </div>

          <div className="goal-footnote">
            <CheckCircle2 size={16} />
            <p>
              Success probability comes from 1,200 Monte Carlo paths using the goal&apos;s expected return and 12% annual volatility.
              It is a planning estimate, not a market forecast. A goal without a deadline is tracked but not scored.
            </p>
          </div>

          <div className="dashboard-grid">
            <Card>
              <SectionTitle title="What moves the needle" description="Fix the funding gap before changing the expected return." />
              <div className="principle-list">
                <div>
                  <span className="principle-number">01</span>
                  <div><strong>Increase the monthly amount first.</strong><p>Contribution changes have a larger, more reliable effect than optimistic return assumptions.</p></div>
                </div>
                <div>
                  <span className="principle-number">02</span>
                  <div><strong>Protect the emergency buffer.</strong><p>A goal funded by cash you may need next month is not really funded.</p></div>
                </div>
                <div>
                  <span className="principle-number">03</span>
                  <div><strong>Use a range, not a single number.</strong><p>The 10th–90th percentile band keeps the plan honest about market uncertainty.</p></div>
                </div>
              </div>
            </Card>
            <Card className="advisor-invite">
              <span className="eyebrow light">ASK THE GROUNDED ADVISOR</span>
              <h2>“Am I on track for {goals[0]?.name}?”</h2>
              <p>The advisor uses the same deterministic goal engine, then explains the arithmetic in plain language.</p>
              <a className="btn btn-dark" href={`/advisor?q=${encodeURIComponent(`Am I on track for ${goals[0]?.name}?`)}`}>
                <Sparkles size={15} /> Discuss this goal <ArrowRight size={14} />
              </a>
            </Card>
          </div>
        </>
      )}

      <GoalModal
        open={formOpen}
        initial={editing}
        currency={currency}
        onClose={() => { setFormOpen(false); setEditing(null) }}
        onSaved={load}
      />
      <GoalDetail
        goalId={detailId}
        currency={currency}
        onClose={() => setDetailId(null)}
        onChanged={load}
      />
    </>
  )
}

function GoalCard({ goal, currency, onEdit, onDelete, onOpen }) {
  const tone = goal.status === 'achieved' ? 'green' : goal.status === 'off_track' || goal.status === 'overdue' ? 'red' : goal.status === 'at_risk' ? 'amber' : 'green'
  return (
    <Card className={`goal-card goal-${statusTone(goal.status)}`}>
      <div className="goal-card-head">
        <span className="goal-avatar"><Target size={18} /></span>
        <div className="goal-card-title">
          <span className="goal-category">{goal.category}</span>
          <h2>{goal.name}</h2>
        </div>
        <div className="row-actions">
          <button type="button" className="icon-btn" onClick={onEdit} aria-label={`Edit ${goal.name}`}><Pencil size={15} /></button>
          <button type="button" className="icon-btn danger" onClick={onDelete} aria-label={`Delete ${goal.name}`}><Trash2 size={15} /></button>
        </div>
      </div>

      <div className="goal-amounts">
        <strong>{formatMoney(goal.saved_amount, currency)}</strong>
        <span>of {formatMoney(goal.target_amount, currency)}</span>
      </div>
      <ProgressBar value={goal.progress_pct} tone={tone} height={10} />
      <div className="goal-progress-meta">
        <Verdict verdict={goal.status}>{GOAL_STATUS_LABELS[goal.status] || titleCase(goal.status)}</Verdict>
        <span>{formatPct(goal.progress_pct, 1)} complete</span>
        <span>{goal.target_date ? formatDate(goal.target_date, 'month') : 'No deadline'}</span>
      </div>

      <div className="goal-metrics">
        <div>
          <span>Monthly plan</span>
          <strong>{formatMoney(goal.monthly_contribution, currency)}</strong>
        </div>
        <div>
          <span>Required</span>
          <strong>{goal.required_monthly ? formatMoney(goal.required_monthly, currency) : '—'}</strong>
        </div>
        <div>
          <span>Success est.</span>
          <strong>{goal.probability == null ? '—' : formatPct(goal.probability * 100, 0)}</strong>
        </div>
      </div>

      {goal.probability != null && (
        <div className="goal-range">
          <div className="range-track">
            <span style={{ left: '10%', right: '10%' }} />
            <i style={{ left: `${Math.max(2, Math.min(98, Number(goal.probability) * 100))}%` }} />
          </div>
          <div className="range-labels">
            <span>P10 {formatMoney(goal.p10, currency, { compact: true })}</span>
            <span>P50 {formatMoney(goal.p50, currency, { compact: true })}</span>
            <span>P90 {formatMoney(goal.p90, currency, { compact: true })}</span>
          </div>
        </div>
      )}

      {Number(goal.monthly_gap) > 0 && goal.status !== 'achieved' && (
        <p className="goal-gap"><TrendingUp size={14} /> Add {formatMoney(goal.monthly_gap, currency)}/month to close the funding gap.</p>
      )}

      <button type="button" className="goal-open" onClick={onOpen}>
        View contributions &amp; plan <ArrowRight size={14} />
      </button>
    </Card>
  )
}

function GoalModal({ open, initial, currency, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(emptyGoal())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(
      initial
        ? {
            name: initial.name || '',
            category: initial.category || 'General',
            target_amount: initial.target_amount || '',
            initial_amount: '',
            monthly_contribution: initial.monthly_contribution || '',
            target_date: initial.target_date || '',
            expected_return: initial.expected_return ?? 8,
            priority: initial.priority ?? 2,
            notes: initial.note || '',
          }
        : emptyGoal(),
    )
  }, [open, initial])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = {
        ...form,
        target_amount: Number(form.target_amount),
        monthly_contribution: Number(form.monthly_contribution || 0),
        expected_return: Number(form.expected_return || 0),
        priority: Number(form.priority),
        target_date: form.target_date || null,
      }
      if (initial) {
        await api.updateGoal(initial.id, payload)
        toast.push('Goal updated.')
      } else {
        payload.initial_amount = Number(form.initial_amount || 0)
        await api.createGoal(payload)
        toast.push('Goal created. Now give it a monthly number.')
      }
      await onSaved()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initial ? `Edit ${initial.name}` : 'Create a goal'}
      eyebrow="A FUTURE WORTH FUNDING"
      size="md"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" form="goal-form" className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label="Saving…" /> : initial ? 'Save changes' : 'Create goal'}
          </button>
        </>
      }
    >
      <form id="goal-form" className="stack-form" onSubmit={submit}>
        <div className="form-grid two">
          <Field label="Goal name" className="span-2">
            <input required maxLength={120} value={form.name} placeholder="Emergency fund" onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </Field>
          <Field label="Category">
            <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
              {GOAL_CATEGORIES.map((category) => <option key={category}>{category}</option>)}
            </select>
          </Field>
          <Field label="Target date" hint="Leave blank for a goal without a deadline.">
            <input type="date" min={todayISO()} value={form.target_date} onChange={(event) => setForm({ ...form, target_date: event.target.value })} />
          </Field>
          <Field label="Target amount">
            <div className="amount-field"><span>₹</span><input type="number" min="1" step="1" required value={form.target_amount} placeholder="500000" onChange={(event) => setForm({ ...form, target_amount: event.target.value })} /></div>
          </Field>
          <Field label={initial ? 'Monthly contribution' : 'Starting amount'}>
            <div className="amount-field">
              <span>₹</span>
              <input
                type="number"
                min="0"
                step="1"
                value={initial ? form.monthly_contribution : form.initial_amount}
                placeholder={initial ? '10000' : '25000'}
                onChange={(event) => setForm({ ...form, [initial ? 'monthly_contribution' : 'initial_amount']: event.target.value })}
              />
            </div>
          </Field>
          <Field label="Expected annual return" hint="Planning assumption, not a guarantee. 8% is a neutral default.">
            <div className="amount-field"><span>%</span><input type="number" min="0" max="30" step="0.5" value={form.expected_return} onChange={(event) => setForm({ ...form, expected_return: event.target.value })} /></div>
          </Field>
          <Field label="Priority">
            <select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
              <option value={1}>High</option>
              <option value={2}>Medium</option>
              <option value={3}>Low</option>
            </select>
          </Field>
          <Field label="Notes" className="span-2">
            <textarea rows={2} maxLength={500} value={form.notes} placeholder="Why this matters, or the rule you will follow." onChange={(event) => setForm({ ...form, notes: event.target.value })} />
          </Field>
        </div>
        {error && <div className="form-error">{error}</div>}
      </form>
    </Modal>
  )
}

function GoalDetail({ goalId, currency, onClose, onChanged }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const [date, setDate] = useState(todayISO())
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!goalId) return
    setLoading(true)
    try {
      setData(await api.goal(goalId))
    } catch (err) {
      toast.push(err.message, 'error')
      onClose()
    } finally {
      setLoading(false)
    }
  }, [goalId, onClose, toast])

  useEffect(() => {
    if (!goalId) {
      setData(null)
      setAmount('')
      setNote('')
      setDate(todayISO())
      return
    }
    load()
  }, [goalId, load])

  async function contribute(event) {
    event.preventDefault()
    if (!Number(amount)) return
    setBusy(true)
    try {
      await api.addContribution(goalId, { amount: Number(amount), note, date })
      toast.push('Contribution recorded. Ten points added.')
      setAmount('')
      setNote('')
      setDate(todayISO())
      await load()
      await onChanged()
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function removeContribution(contribution) {
    try {
      await api.deleteContribution(goalId, contribution.id)
      toast.push('Contribution removed.')
      await load()
      await onChanged()
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  const goal = data?.goal
  const visible = Boolean(goalId)
  return (
    <Modal open={visible} onClose={onClose} title={goal?.name || 'Goal plan'} eyebrow="CONTRIBUTION LEDGER" size="lg">
      {loading || !goal ? (
        <div className="centered-loader"><Spinner label="Loading the goal plan…" /></div>
      ) : (
        <div className="goal-detail">
          <div className="goal-detail-hero">
            <div>
              <span className="eyebrow light">FUNDED SO FAR</span>
              <strong>{formatMoney(goal.saved_amount, currency)}</strong>
              <p>of {formatMoney(goal.target_amount, currency)} · {formatPct(goal.progress_pct, 1)} complete</p>
            </div>
            <div className="goal-detail-meta">
              <Badge tone={statusTone(goal.status)}>{GOAL_STATUS_LABELS[goal.status] || titleCase(goal.status)}</Badge>
              <span>{goal.target_date ? `Target ${formatDate(goal.target_date)}` : 'No deadline'}</span>
              <span>{goal.months_left == null ? 'Open-ended' : `${goal.months_left} months left`}</span>
            </div>
          </div>

          <div className="key-stat-row">
            <div><span>Monthly contribution</span><strong>{formatMoney(goal.monthly_contribution, currency)}</strong></div>
            <div><span>Required to hit target</span><strong>{goal.required_monthly ? formatMoney(goal.required_monthly, currency) : '—'}</strong></div>
            <div><span>Projected value</span><strong>{goal.projected_value ? formatMoney(goal.projected_value, currency) : '—'}</strong></div>
            <div><span>Success estimate</span><strong>{goal.probability == null ? '—' : formatPct(goal.probability * 100, 0)}</strong></div>
          </div>

          <form className="inline-contribution" onSubmit={contribute}>
            <div>
              <span className="eyebrow">RECORD A CONTRIBUTION</span>
              <p>Move money you have already saved, not money you intend to save.</p>
            </div>
            <div className="amount-field"><span>₹</span><input type="number" min="1" step="1" required placeholder="5000" value={amount} onChange={(event) => setAmount(event.target.value)} /></div>
            <input type="date" value={date} max={todayISO()} onChange={(event) => setDate(event.target.value)} aria-label="Contribution date" />
            <input placeholder="Optional note" maxLength={300} value={note} onChange={(event) => setNote(event.target.value)} aria-label="Contribution note" />
            <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : <Plus size={15} />} Add</button>
          </form>

          <div className="contribution-list">
            {(data.contributions || []).length === 0 ? (
              <EmptyState title="No contributions recorded">Add the first contribution to make progress measurable.</EmptyState>
            ) : (
              data.contributions.map((contribution) => (
                <div className="contribution-row" key={contribution.id}>
                  <span className="contribution-dot"><CircleDollarSign size={16} /></span>
                  <div>
                    <strong>{formatMoney(contribution.amount, currency)}</strong>
                    <small>{formatDate(contribution.date)} · {contribution.note || 'Contribution'}</small>
                  </div>
                  <button type="button" className="icon-btn danger" onClick={() => removeContribution(contribution)} aria-label="Delete contribution"><Trash2 size={14} /></button>
                </div>
              ))
            )}
          </div>

          {goal.projected_value && (
            <div className="assumption-note">
              <Sparkles size={15} />
              <p>
                Projection assumes {goal.expected_return}% annual return and {formatMoney(goal.monthly_contribution, currency)} per month.
                {Number(goal.shortfall) > 0 ? ` It leaves a projected shortfall of ${formatMoney(goal.shortfall, currency)}.` : ' It fully funds the target at the expected return.'}
              </p>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

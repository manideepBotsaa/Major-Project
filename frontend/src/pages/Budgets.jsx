import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  Copy,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  TriangleAlert,
  WalletCards,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { EXPENSE_CATEGORIES } from '../lib/constants'
import { currentMonth, formatMoney, formatMonthKey, formatPct, shiftMonth, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, Field, Modal, PageHeader, ProgressBar, SectionTitle, Spinner, statusTone } from '../components/UI'

function monthLabel(month) {
  return formatMonthKey(month)
}

export default function Budgets() {
  const { user } = useAuth()
  const toast = useToast()
  const [month, setMonth] = useState(currentMonth())
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)
  const [copying, setCopying] = useState(false)
  const currency = user?.currency || 'INR'

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await api.budgets(month))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [month])

  useEffect(() => {
    load()
  }, [load])

  async function copyLastMonth() {
    setCopying(true)
    try {
      const source = shiftMonth(month, -1)
      const result = await api.copyBudgets({ from_month: source, to_month: month })
      toast.push(result.copied ? `Copied ${result.copied} budgets from ${monthLabel(source)}.` : `No budgets found in ${monthLabel(source)}.`, result.copied ? 'success' : 'info')
      await load()
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setCopying(false)
    }
  }

  async function useSuggestion(suggestion) {
    setBusy(suggestion.category)
    try {
      await api.createBudget({ category: suggestion.category, amount: suggestion.suggested, month })
      toast.push(`${suggestion.category} budget set at ${formatMoney(suggestion.suggested, currency)}.`)
      await load()
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setBusy('')
    }
  }

  async function removeBudget(budget) {
    if (!window.confirm(`Remove the ${budget.category} budget for ${monthLabel(month)}?`)) return
    try {
      await api.deleteBudget(budget.id)
      toast.push('Budget removed.')
      await load()
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  const status = data?.status
  const budgets = status?.categories || []
  const suggestions = data?.suggestions || []
  const unbudgeted = status?.unbudgeted || []
  const currentMonthValue = currentMonth()

  return (
    <>
      <PageHeader
        eyebrow="PLAN WITH A NUMBER, NOT A FEELING"
        title="Budgets"
        description="A budget is a decision made once. Daily remaining is the number that changes behaviour."
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={copyLastMonth} disabled={copying}>
              {copying ? <Spinner /> : <Copy size={16} />} Copy last month
            </button>
            <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setModalOpen(true) }}>
              <Plus size={16} /> Add budget
            </button>
          </>
        }
      />

      <div className="month-switcher">
        <button type="button" className="icon-btn" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
          <ChevronLeft size={18} />
        </button>
        <div>
          <CalendarRange size={16} />
          <strong>{monthLabel(month)}</strong>
          {month !== currentMonthValue && (
            <button type="button" className="text-link small" onClick={() => setMonth(currentMonthValue)}>Back to current</button>
          )}
        </div>
        <button type="button" className="icon-btn" onClick={() => setMonth(shiftMonth(month, 1))} disabled={month >= shiftMonth(currentMonthValue, 2)} aria-label="Next month">
          <ChevronRight size={18} />
        </button>
        <input type="month" value={month} onChange={(event) => event.target.value && setMonth(event.target.value)} aria-label="Choose month" />
      </div>

      {loading ? (
        <div className="centered-loader"><Spinner label="Loading budget plan…" /></div>
      ) : error ? (
        <Card><EmptyState icon={WalletCards} title="Could not load budgets">{error}</EmptyState></Card>
      ) : (
        <>
          <div className="budget-hero">
            <div className="budget-hero-main">
              <span className="eyebrow light">MONTHLY PLAN</span>
              <h2>{formatMoney(status.total_budget, currency)}</h2>
              <p>{formatMoney(status.total_spent, currency)} spent · {formatMoney(status.total_remaining, currency)} remaining</p>
              <ProgressBar
                value={status.total_spent}
                max={status.total_budget || 1}
                tone={status.overall_state === 'over' ? 'red' : status.overall_state === 'watch' ? 'amber' : 'sand'}
                height={10}
              />
              <div className="budget-hero-legend">
                <span>{formatPct(Number(status.total_spent) / Math.max(1, Number(status.total_budget)) * 100, 0)} of plan used</span>
                <span>{status.elapsed_days} of {status.days_in_month} days elapsed</span>
              </div>
            </div>
            <div className="budget-hero-stats">
              <div>
                <span>Status</span>
                <Badge tone={statusTone(status.overall_state)} dot>{titleCase(status.overall_state)}</Badge>
              </div>
              <div>
                <span>Projected month-end</span>
                <strong>{formatMoney(status.projected_total, currency)}</strong>
              </div>
              <div>
                <span>Over / watch</span>
                <strong>{status.over_count} / {status.watch_count}</strong>
              </div>
              <Link to="/insights" className="btn btn-ghost btn-sm light-link">
                Safe-to-spend model <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          <div className="dashboard-grid">
            <Card>
              <SectionTitle
                title="Category plans"
                description="Pace compares spend against the share of the month elapsed."
                action={<span className="period-chip">{budgets.length} categories</span>}
              />
              {budgets.length ? (
                <div className="budget-list">
                  {budgets.map((budget) => {
                    const pct = budget.used_pct
                    const tone = budget.state === 'over' ? 'red' : budget.state === 'watch' ? 'amber' : 'green'
                    return (
                      <div className="budget-row" key={budget.id}>
                        <div className="budget-row-top">
                          <div>
                            <strong>{budget.category}</strong>
                            <small>
                              {formatMoney(budget.spent, currency)} of {formatMoney(budget.amount, currency)}
                              {Number(budget.remaining) < 0 ? ` · ${formatMoney(Math.abs(budget.remaining), currency)} over` : ` · ${formatMoney(budget.remaining, currency)} left`}
                            </small>
                          </div>
                          <div className="budget-row-actions">
                            <Badge tone={statusTone(budget.state)}>{titleCase(budget.state)}</Badge>
                            <button type="button" className="icon-btn subtle" onClick={() => { setEditing(budget); setModalOpen(true) }} aria-label={`Edit ${budget.category} budget`}>
                              <Pencil size={14} />
                            </button>
                            <button type="button" className="icon-btn subtle danger" onClick={() => removeBudget(budget)} aria-label={`Delete ${budget.category} budget`}>
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                        <ProgressBar value={pct} tone={tone} />
                        <div className="budget-row-foot">
                          <span>{formatPct(pct, 0)}</span>
                          <span>{budget.days_left} days left</span>
                          <span>{formatMoney(budget.daily_remaining, currency)}/day available</span>
                          <span>projected {formatMoney(budget.projected, currency)}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <EmptyState icon={WalletCards} title={`No budgets for ${monthLabel(month)}`}>
                  Start with the three categories where money actually leaks: food, groceries and shopping.
                </EmptyState>
              )}

              {unbudgeted.length > 0 && (
                <div className="unbudgeted">
                  <div className="unbudgeted-head">
                    <TriangleAlert size={16} />
                    <strong>Unbudgeted spending this month</strong>
                  </div>
                  <div className="unbudgeted-chips">
                    {unbudgeted.map((item) => (
                      <span key={item.category}>
                        {item.category} <strong>{formatMoney(item.spent, currency)}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            <div className="stack-column">
              <Card className="suggestions-card">
                <SectionTitle
                  title="Suggested starting points"
                  description="Typical active-month spend × 1.05, rounded to ₹100."
                  action={<Sparkles size={17} />}
                />
                {suggestions.length ? (
                  <div className="suggestion-list">
                    {suggestions.slice(0, 8).map((suggestion) => (
                      <div key={suggestion.category} className="suggestion-row">
                        <div>
                          <strong>{suggestion.category}</strong>
                          <small>
                            {formatMoney(suggestion.median_spend, currency)} typical · {suggestion.months_active}/{suggestion.months_observed} active months
                          </small>
                        </div>
                        <div>
                          <strong>{formatMoney(suggestion.suggested, currency)}</strong>
                          <button type="button" className="btn btn-secondary btn-xs" onClick={() => useSuggestion(suggestion)} disabled={busy === suggestion.category}>
                            {busy === suggestion.category ? <Spinner /> : suggestion.is_set ? 'Update' : 'Use'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="Not enough history">
                    Record a few months of spending and suggestions will appear here.
                  </EmptyState>
                )}
              </Card>

              <Card className="plain-note-card">
                <WalletCards size={20} />
                <div>
                  <strong>How the daily number is computed</strong>
                  <p>
                    Remaining budget is divided by remaining days. Upcoming recurring subscriptions are reserved separately in
                    your safe-to-spend figure, so a subscription due tomorrow does not masquerade as spending money.
                  </p>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}

      <BudgetModal
        open={modalOpen}
        initial={editing}
        month={month}
        currency={currency}
        onClose={() => { setModalOpen(false); setEditing(null) }}
        onSaved={load}
      />
    </>
  )
}

function BudgetModal({ open, initial, month, currency, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState({ category: EXPENSE_CATEGORIES[0], amount: '', rollover: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(
      initial
        ? { category: initial.category, amount: initial.amount, rollover: Boolean(initial.rollover) }
        : { category: EXPENSE_CATEGORIES[0], amount: '', rollover: false },
    )
  }, [open, initial])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (initial) await api.updateBudget(initial.id, { amount: form.amount, rollover: form.rollover })
      else await api.createBudget({ ...form, amount: form.amount, month })
      toast.push(initial ? 'Budget updated.' : 'Budget created.')
      onSaved()
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
      title={initial ? `Edit ${initial.category}` : 'Add a category budget'}
      eyebrow={formatMonthKey(month).toUpperCase()}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" form="budget-form" className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label="Saving…" /> : initial ? 'Save budget' : 'Create budget'}
          </button>
        </>
      }
    >
      <form id="budget-form" className="stack-form" onSubmit={submit}>
        <Field label="Category">
          <select value={form.category} disabled={Boolean(initial)} onChange={(event) => setForm({ ...form, category: event.target.value })}>
            {EXPENSE_CATEGORIES.map((category) => <option key={category}>{category}</option>)}
          </select>
        </Field>
        <Field label="Monthly amount" hint="Use a realistic ceiling, not an aspirational one.">
          <div className="amount-field">
            <span>{currency === 'INR' ? '₹' : currency}</span>
            <input
              type="number"
              min="1"
              step="1"
              required
              autoFocus
              placeholder="9000"
              value={form.amount}
              onChange={(event) => setForm({ ...form, amount: event.target.value })}
            />
          </div>
        </Field>
        <label className="check-row">
          <input type="checkbox" checked={form.rollover} onChange={(event) => setForm({ ...form, rollover: event.target.checked })} />
          <span>
            <strong>Roll over unspent money</strong>
            <small>Carry the unspent balance into next month rather than treating it as free money.</small>
          </span>
        </label>
        {error && <div className="form-error">{error}</div>}
      </form>
    </Modal>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BadgePercent,
  CalendarClock,
  CreditCard,
  Pencil,
  Plus,
  Scale,
  ShieldAlert,
  Sparkles,
  Swords,
  Trash2,
  TrendingDown,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { DEBT_TYPES } from '../lib/constants'
import { formatMoney, formatPct, titleCase } from '../lib/format'
import {
  Badge,
  Callout,
  Card,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  SectionTitle,
  Spinner,
  StatCard,
} from '../components/UI'

function emptyDebt() {
  return { name: '', debt_type: 'credit_card', balance: '', apr: '18', minimum_payment: '', due_day: '', credit_limit: '' }
}

export default function Debts() {
  const { user } = useAuth()
  const toast = useToast()
  const currency = user?.currency || 'INR'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [extra, setExtra] = useState(0)
  const [extraDraft, setExtraDraft] = useState('5000')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async (extraValue = extra) => {
    setError('')
    try {
      setData(await api.debts(extraValue))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [extra])

  useEffect(() => {
    load(extra)
  }, [extra, load])

  async function remove(debt) {
    if (!window.confirm(`Remove “${debt.name}” from your debt plan?`)) return
    try {
      await api.deleteDebt(debt.id)
      toast.push('Debt removed.')
      await load(extra)
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  function applyExtra(event) {
    event.preventDefault()
    setExtra(Math.max(0, Number(extraDraft) || 0))
  }

  const debts = data?.debts || []
  const plan = data?.plan
  const total = useMemo(() => debts.reduce((sum, debt) => sum + Number(debt.balance), 0), [debts])
  const minimum = useMemo(() => debts.reduce((sum, debt) => sum + Number(debt.minimum_payment), 0), [debts])
  const weightedApr = total ? debts.reduce((sum, debt) => sum + Number(debt.balance) * Number(debt.apr), 0) / total : 0
  const avalanche = plan?.avalanche
  const snowball = plan?.snowball
  const baseline = plan?.baseline

  return (
    <>
      <PageHeader
        eyebrow="THE MOST EXPENSIVE MONEY IS THE MONEY YOU OWE"
        title="Debt"
        description="Compare interest saved against momentum gained. The arithmetic is deterministic; the strategy is yours."
        actions={<button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setModalOpen(true) }}><Plus size={16} /> Add debt</button>}
      />

      {loading ? (
        <div className="centered-loader"><Spinner label="Building your payoff plan…" /></div>
      ) : error ? (
        <Card><EmptyState icon={CreditCard} title="Could not load your debts">{error}</EmptyState></Card>
      ) : debts.length === 0 ? (
        <Card>
          <EmptyState icon={CreditCard} title="No debts tracked" action={<button type="button" className="btn btn-primary btn-sm" onClick={() => setModalOpen(true)}><Plus size={15} /> Add a debt</button>}>
            Add a balance, APR and minimum payment. The payoff comparison will explain what each strategy costs.
          </EmptyState>
        </Card>
      ) : (
        <>
          <div className="stat-grid four">
            <StatCard label="Total balance" value={formatMoney(total, currency)} icon={CreditCard} note={`${debts.length} debt${debts.length === 1 ? '' : 's'} tracked`} tone="clay" />
            <StatCard label="Monthly minimums" value={formatMoney(minimum, currency)} icon={CalendarClock} note="Before any extra payment" tone="sand" />
            <StatCard label="Weighted APR" value={formatPct(weightedApr, 1)} icon={BadgePercent} note="Balance-weighted average rate" tone="rose" />
            <StatCard
              label={avalanche ? 'Debt-free in' : 'Plan unavailable'}
              value={avalanche?.months == null ? '—' : avalanche.months === 0 ? 'Done' : `${avalanche.years} yr`}
              icon={TrendingDown}
              note={avalanche?.total_interest != null ? `${formatMoney(avalanche.total_interest, currency)} projected interest` : 'Add a valid payment'}
              tone="green"
            />
          </div>

          {debts.some((debt) => Number(debt.minimum_payment) <= Number(debt.balance) * Number(debt.apr) / 1200) && (
            <Callout tone="red" title="A minimum payment is not covering interest" icon={ShieldAlert}>
              <p>One or more payments will never reduce the balance. Increase the payment before optimising strategy.</p>
            </Callout>
          )}

          <div className="dashboard-grid">
            <Card>
              <SectionTitle title="Your debts" description="Highest APR first. Credit utilisation appears where a limit is known." />
              <div className="debt-list">
                {debts.map((debt) => (
                  <div className="debt-row" key={debt.id}>
                    <span className={`debt-icon apr-${debt.apr >= 18 ? 'high' : debt.apr >= 10 ? 'mid' : 'low'}`}><CreditCard size={18} /></span>
                    <div className="debt-main">
                      <div>
                        <strong>{debt.name}</strong>
                        <small>{DEBT_TYPES.find((type) => type.value === debt.debt_type)?.label || titleCase(debt.debt_type)} · Min {formatMoney(debt.minimum_payment, currency)}</small>
                      </div>
                      <div className="debt-numbers">
                        <span><strong>{formatMoney(debt.balance, currency)}</strong> balance</span>
                        <span><strong>{formatPct(debt.apr, 1)}</strong> APR</span>
                        {debt.utilization != null && <span><strong>{formatPct(debt.utilization, 0)}</strong> used</span>}
                      </div>
                    </div>
                    <div className="row-actions">
                      <button type="button" className="icon-btn" onClick={() => { setEditing(debt); setModalOpen(true) }} aria-label={`Edit ${debt.name}`}><Pencil size={15} /></button>
                      <button type="button" className="icon-btn danger" onClick={() => remove(debt)} aria-label={`Remove ${debt.name}`}><Trash2 size={15} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <div className="stack-column">
              <Card className="extra-payment-card">
                <SectionTitle title="Add a monthly extra" description="Every extra rupee goes to the priority debt." action={<Sparkles size={17} />} />
                <form className="extra-form" onSubmit={applyExtra}>
                  <div className="amount-field"><span>₹</span><input type="number" min="0" step="500" value={extraDraft} onChange={(event) => setExtraDraft(event.target.value)} /></div>
                  <button type="submit" className="btn btn-primary">Apply</button>
                </form>
                <div className="extra-stats">
                  <div><span>Monthly outlay</span><strong>{avalanche ? formatMoney(avalanche.monthly_outlay, currency) : '—'}</strong></div>
                  <div><span>Interest saved</span><strong>{plan ? formatMoney(plan.interest_saved_vs_baseline, currency) : '—'}</strong></div>
                  <div><span>Months saved</span><strong>{plan?.months_saved_vs_baseline ?? '—'}</strong></div>
                </div>
              </Card>
              <Card className="plain-note-card">
                <Scale size={20} />
                <div>
                  <strong>Avalanche vs snowball</strong>
                  <p>
                    Avalanche targets the highest APR and minimises interest. Snowball targets the smallest balance and
                    produces faster closed accounts. The app shows both; it does not pretend one is universally right.
                  </p>
                </div>
              </Card>
            </div>
          </div>

          {plan && (
            <section className="section-block">
              <SectionTitle title="Two honest payoff paths" description={`Comparison assumes ${formatMoney(extra, currency)} extra each month and no new borrowing.`} />
              <div className="strategy-grid">
                <StrategyCard
                  title="Avalanche"
                  subtitle="Lowest total interest"
                  icon={TrendingDown}
                  plan={avalanche}
                  baseline={baseline}
                  currency={currency}
                  featured
                />
                <StrategyCard title="Snowball" subtitle="Fastest first win" icon={Swords} plan={snowball} baseline={baseline} currency={currency} />
              </div>
              {avalanche?.order?.length > 0 && (
                <Card className="payoff-order">
                  <SectionTitle title="Attack order" description="This is the deterministic order produced by the selected strategy." />
                  <ol>
                    {avalanche.order.map((name, index) => (
                      <li key={name}><span>{String(index + 1).padStart(2, '0')}</span><strong>{name}</strong>{index === 0 && <Badge tone="red">Highest APR</Badge>}</li>
                    ))}
                  </ol>
                </Card>
              )}
            </section>
          )}

          <Card className="advisor-invite compact-invite">
            <div>
              <span className="eyebrow light">A HARD QUESTION, ANSWERED HONESTLY</span>
              <h2>Is it worth investing while carrying this debt?</h2>
              <p>Ask the advisor to compare the guaranteed cost of interest with uncertain investment returns.</p>
            </div>
            <a className="btn btn-dark" href={`/advisor?q=${encodeURIComponent('How do I become debt-free faster?')}`}>
              Discuss my debt <ArrowRight size={14} />
            </a>
          </Card>
        </>
      )}

      <DebtModal open={modalOpen} initial={editing} onClose={() => { setModalOpen(false); setEditing(null) }} onSaved={() => load(extra)} />
    </>
  )
}

function StrategyCard({ title, subtitle, icon: Icon, plan, baseline, currency, featured }) {
  if (!plan) return null
  const monthsSaved = baseline ? Math.max(0, (baseline.months || 0) - (plan.months || 0)) : 0
  return (
    <Card className={`strategy-card ${featured ? 'strategy-featured' : ''}`}>
      <div className="strategy-head">
        <span><Icon size={18} /></span>
        <div><h3>{title}</h3><p>{subtitle}</p></div>
        {featured && <Badge tone="green">Recommended by arithmetic</Badge>}
      </div>
      <div className="strategy-hero">
        <strong>{plan.months == null ? 'Never' : plan.months === 0 ? 'Paid off' : `${plan.months} months`}</strong>
        <span>{plan.months == null ? 'The payment does not amortise' : `Debt-free in about ${plan.years} years`}</span>
      </div>
      <div className="strategy-stats">
        <div><span>Total interest</span><strong>{plan.total_interest == null ? '—' : formatMoney(plan.total_interest, currency)}</strong></div>
        <div><span>Total paid</span><strong>{plan.total_paid == null ? '—' : formatMoney(plan.total_paid, currency)}</strong></div>
        <div><span>Vs minimums</span><strong>{formatMoney(Math.max(0, (baseline?.total_interest || 0) - (plan.total_interest || 0)), currency)} saved</strong></div>
        <div><span>Time saved</span><strong>{monthsSaved} months</strong></div>
      </div>
    </Card>
  )
}

function DebtModal({ open, initial, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(emptyDebt())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(
      initial
        ? {
            name: initial.name,
            debt_type: initial.debt_type,
            balance: initial.balance,
            apr: initial.apr,
            minimum_payment: initial.minimum_payment,
            due_day: initial.due_day ?? '',
            credit_limit: initial.credit_limit ?? '',
          }
        : emptyDebt(),
    )
  }, [open, initial])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = {
        ...form,
        balance: Number(form.balance),
        apr: Number(form.apr),
        minimum_payment: Number(form.minimum_payment),
        due_day: form.due_day === '' ? null : Number(form.due_day),
        credit_limit: form.credit_limit === '' ? null : Number(form.credit_limit),
      }
      if (initial) await api.updateDebt(initial.id, payload)
      else await api.createDebt(payload)
      toast.push(initial ? 'Debt updated.' : 'Debt added. The payoff plan is recalculated.')
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
      title={initial ? `Edit ${initial.name}` : 'Add a debt'}
      eyebrow="THE BALANCE, RATE AND MINIMUM"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" form="debt-form" className="btn btn-primary" disabled={busy}>{busy ? <Spinner label="Saving…" /> : 'Save debt'}</button>
        </>
      }
    >
      <form id="debt-form" className="stack-form" onSubmit={submit}>
        <div className="form-grid two">
          <Field label="Debt name" className="span-2">
            <input required maxLength={120} value={form.name} placeholder="HDFC credit card" onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </Field>
          <Field label="Type">
            <select value={form.debt_type} onChange={(event) => setForm({ ...form, debt_type: event.target.value })}>
              {DEBT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </Field>
          <Field label="Current balance">
            <div className="amount-field"><span>₹</span><input type="number" min="0" step="1" required value={form.balance} onChange={(event) => setForm({ ...form, balance: event.target.value })} /></div>
          </Field>
          <Field label="Annual interest rate" hint="APR, not the monthly rate.">
            <div className="amount-field"><span>%</span><input type="number" min="0" max="100" step="0.1" required value={form.apr} onChange={(event) => setForm({ ...form, apr: event.target.value })} /></div>
          </Field>
          <Field label="Minimum payment">
            <div className="amount-field"><span>₹</span><input type="number" min="1" step="1" required value={form.minimum_payment} onChange={(event) => setForm({ ...form, minimum_payment: event.target.value })} /></div>
          </Field>
          <Field label="Due day" hint="Optional. 1–31.">
            <input type="number" min="1" max="31" value={form.due_day} onChange={(event) => setForm({ ...form, due_day: event.target.value })} />
          </Field>
          <Field label="Credit limit" hint="Optional. Used for utilisation.">
            <div className="amount-field"><span>₹</span><input type="number" min="0" step="1" value={form.credit_limit} onChange={(event) => setForm({ ...form, credit_limit: event.target.value })} /></div>
          </Field>
        </div>
        {error && <div className="form-error">{error}</div>}
      </form>
    </Modal>
  )
}

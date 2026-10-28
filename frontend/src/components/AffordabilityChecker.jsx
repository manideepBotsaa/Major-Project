import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Landmark, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react'
import { api } from '../api'
import { formatMoney, titleCase } from '../lib/format'
import { EXPENSE_CATEGORIES } from '../lib/constants'
import { Badge, Spinner, statusTone } from './UI'

export default function AffordabilityChecker({ currency = 'INR', initialAmount = '', compact = false }) {
  const [form, setForm] = useState({
    amount: initialAmount,
    category: 'Shopping',
    finance: false,
    apr: '14',
    months: '6',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    if (!Number(form.amount)) {
      setError('Enter a purchase amount first.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const payload = {
        amount: Number(form.amount),
        category: form.category,
        purpose: 'purchase',
      }
      if (form.finance) {
        payload.apr = Number(form.apr)
        payload.months = Number(form.months)
      }
      setResult(await api.affordability(payload))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`affordability ${compact ? 'affordability-compact' : ''}`}>
      <form className="affordability-form" onSubmit={submit}>
        <div className="affordability-input">
          <span>{currency === 'INR' ? '₹' : currency}</span>
          <input
            type="number"
            min="1"
            step="1"
            inputMode="decimal"
            placeholder="25,000"
            value={form.amount}
            onChange={(event) => {
              setForm({ ...form, amount: event.target.value })
              setResult(null)
            }}
            aria-label="Purchase amount"
          />
        </div>
        <select
          value={form.category}
          onChange={(event) => setForm({ ...form, category: event.target.value })}
          aria-label="Purchase category"
        >
          {EXPENSE_CATEGORIES.map((category) => (
            <option key={category}>{category}</option>
          ))}
        </select>
        <button type="submit" className="btn btn-dark" disabled={busy}>
          {busy ? <Spinner /> : <Sparkles size={15} />}
          {busy ? 'Checking' : 'Check'}
        </button>
      </form>

      <label className="finance-toggle">
        <input
          type="checkbox"
          checked={form.finance}
          onChange={(event) => {
            setForm({ ...form, finance: event.target.checked })
            setResult(null)
          }}
        />
        <span>I would finance it with EMI</span>
      </label>
      {form.finance && (
        <div className="finance-fields">
          <label>
            APR %
            <input
              type="number"
              min="0"
              max="60"
              step="0.1"
              value={form.apr}
              onChange={(event) => setForm({ ...form, apr: event.target.value })}
            />
          </label>
          <label>
            Months
            <input
              type="number"
              min="1"
              max="84"
              value={form.months}
              onChange={(event) => setForm({ ...form, months: event.target.value })}
            />
          </label>
        </div>
      )}

      {error && <p className="inline-error">{error}</p>}

      {result && (
        <div className="affordability-result">
          <div className="affordability-verdict">
            <Badge tone={statusTone(result.verdict)}>{result.label}</Badge>
            <strong>{formatMoney(result.amount, currency)}</strong>
          </div>
          <div className="affordability-breakdown">
            <div>
              <span>Comfort ceiling</span>
              <strong>{formatMoney(result.max_safe_amount, currency)}</strong>
            </div>
            <div>
              <span>Discretionary left</span>
              <strong>{formatMoney(result.breakdown.discretionary_remaining, currency)}</strong>
            </div>
            <div>
              <span>Emergency runway</span>
              <strong>{result.breakdown.emergency_months} months</strong>
            </div>
          </div>
          {result.financing && (
            <div className="finance-result">
              <Landmark size={17} />
              <div>
                <strong>
                  {formatMoney(result.financing.monthly_payment, currency)}/month for {result.financing.months} months
                </strong>
                <span>
                  {formatMoney(result.financing.total_interest, currency)} in interest ·{' '}
                  {titleCase(result.financing.verdict)}
                </span>
              </div>
            </div>
          )}
          {result.goal_impact?.delay_months && (
            <p className="affordability-goal">
              This would delay <strong>{result.goal_impact.goal}</strong> by about{' '}
              {result.goal_impact.delay_months} months.
            </p>
          )}
          {!compact && result.alternatives?.length > 0 && (
            <ul className="alternative-list">
              {result.alternatives.map((alternative) => (
                <li key={alternative.option}>
                  {result.verdict === 'not_now' ? <TriangleAlert size={14} /> : <CheckCircle2 size={14} />}
                  <div>
                    <strong>{alternative.option}</strong>
                    <span>{alternative.detail}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="affordability-foot">
            <span>
              <ShieldCheck size={13} /> Computed locally from your budgets and cash assets
            </span>
            <Link to={`/advisor?q=${encodeURIComponent(`Can I afford a ${formatMoney(result.amount, currency)} ${result.category.toLowerCase()} purchase?`)}`}>
              Discuss it <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

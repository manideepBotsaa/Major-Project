import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'
import { EXPENSE_CATEGORIES, INCOME_CATEGORIES } from '../lib/constants'
import { todayISO } from '../lib/format'
import { Field, Modal, Spinner } from './UI'

function blankForm() {
  return {
    kind: 'expense',
    amount: '',
    category: 'Food & Dining',
    description: '',
    notes: '',
    date: todayISO(),
    recurring: false,
  }
}

export default function TransactionModal({ open, initial, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(blankForm)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [suggesting, setSuggesting] = useState(false)
  const editing = Boolean(initial?.id)

  useEffect(() => {
    if (!open) return
    setError('')
    setSuggestion(null)
    if (initial) {
      setForm({
        kind: initial.kind,
        amount: initial.amount,
        category: initial.category,
        description: initial.description || '',
        notes: initial.notes || '',
        date: initial.date,
        recurring: Boolean(initial.recurring),
      })
    } else {
      setForm(blankForm())
    }
  }, [open, initial])

  const categories = form.kind === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES

  function changeKind(kind) {
    const nextCategories = kind === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES
    setForm({
      ...form,
      kind,
      category: nextCategories.includes(form.category) ? form.category : nextCategories[0],
    })
    setSuggestion(null)
  }

  async function suggestCategory() {
    if (!form.description.trim()) {
      setError('Add a description first, then ask for a category suggestion.')
      return
    }
    setSuggesting(true)
    setError('')
    try {
      const result = await api.suggestCategory({ description: form.description, kind: form.kind })
      setSuggestion(result)
      if (result.category && categories.includes(result.category)) {
        setForm((current) => ({ ...current, category: result.category }))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSuggesting(false)
    }
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await api.saveTransaction(
        { ...form, amount: String(form.amount), recurring: Boolean(form.recurring) },
        initial?.id,
      )
      toast.push(editing ? 'Transaction updated.' : 'Transaction saved.')
      onSaved?.(result.transaction)
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
      title={editing ? 'Edit transaction' : 'Add transaction'}
      eyebrow="LEDGER ENTRY"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" form="transaction-form" className="btn btn-primary" disabled={busy}>
            {busy ? <Spinner label="Saving…" /> : editing ? 'Save changes' : 'Add transaction'}
          </button>
        </>
      }
    >
      <form id="transaction-form" className="stack-form" onSubmit={submit}>
        <div className="segmented">
          <button type="button" className={form.kind === 'expense' ? 'active' : ''} onClick={() => changeKind('expense')}>
            Expense
          </button>
          <button type="button" className={form.kind === 'income' ? 'active' : ''} onClick={() => changeKind('income')}>
            Income
          </button>
        </div>
        <div className="form-grid two">
          <Field label="Amount" hint="INR, two decimal places">
            <div className="amount-field">
              <span>₹</span>
              <input
                type="number"
                min="0.01"
                step="0.01"
                required
                autoFocus
                placeholder="0.00"
                value={form.amount}
                onChange={(event) => setForm({ ...form, amount: event.target.value })}
              />
            </div>
          </Field>
          <Field label="Date">
            <input
              type="date"
              required
              value={form.date}
              onChange={(event) => setForm({ ...form, date: event.target.value })}
            />
          </Field>
        </div>
        <Field label="Category">
          <div className="field-with-action">
            <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
              {categories.map((category) => (
                <option key={category}>{category}</option>
              ))}
            </select>
            {form.kind === 'expense' && (
              <button type="button" className="btn btn-secondary btn-sm" onClick={suggestCategory} disabled={suggesting}>
                {suggesting ? <Spinner /> : <Sparkles size={14} />} Suggest
              </button>
            )}
          </div>
        </Field>
        {suggestion && (
          <p className="suggest-note">
            Suggested <strong>{suggestion.category}</strong> from {suggestion.source} signals ·{' '}
            {Math.round((suggestion.confidence || 0) * 100)}% confidence
          </p>
        )}
        <Field label="Description">
          <input
            maxLength={200}
            placeholder="e.g. Weekly groceries at DMart"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </Field>
        <Field label="Notes" hint="Optional. Encrypted at rest.">
          <textarea
            rows={3}
            maxLength={1000}
            placeholder="Anything worth remembering about this entry"
            value={form.notes}
            onChange={(event) => setForm({ ...form, notes: event.target.value })}
          />
        </Field>
        <label className="check-row">
          <input
            type="checkbox"
            checked={form.recurring}
            onChange={(event) => setForm({ ...form, recurring: event.target.checked })}
          />
          <span>
            <strong>Recurring transaction</strong>
            <small>Mark regular bills, rent or subscriptions.</small>
          </span>
        </label>
        {error && <div className="form-error">{error}</div>}
      </form>
    </Modal>
  )
}

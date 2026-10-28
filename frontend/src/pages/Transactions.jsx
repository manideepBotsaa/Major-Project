import { useEffect, useRef, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ChevronLeft,
  ChevronRight,
  Download,
  FileUp,
  Pencil,
  Plus,
  ReceiptText,
  Search,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { EXPENSE_CATEGORIES, INCOME_CATEGORIES } from '../lib/constants'
import { formatDate, formatMoney, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, PageHeader, Spinner } from '../components/UI'
import TransactionModal from '../components/TransactionModal'

const ALL_CATEGORIES = [...EXPENSE_CATEGORIES, ...INCOME_CATEGORIES]

export default function Transactions() {
  const { user } = useAuth()
  const toast = useToast()
  const fileInput = useRef(null)
  const [rows, setRows] = useState([])
  const [meta, setMeta] = useState({ total: 0, page: 1, per_page: 25, has_more: false })
  const [filters, setFilters] = useState({ q: '', kind: '', category: '', page: 1 })
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const currency = user?.currency || 'INR'

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFilters((current) => (current.q === query ? current : { ...current, q: query, page: 1 }))
    }, 280)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api
      .transactions({ ...filters, per_page: 25 })
      .then((data) => {
        if (!active) return
        setRows(data.transactions)
        setMeta({ total: data.total, page: data.page, per_page: data.per_page, has_more: data.has_more })
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [filters])

  function patchFilters(next) {
    setFilters((current) => ({ ...current, ...next, page: next.page ?? 1 }))
  }

  async function remove(transaction) {
    if (!window.confirm(`Delete “${transaction.description || transaction.category}” for ${formatMoney(transaction.amount, currency)}?`)) return
    try {
      await api.deleteTransaction(transaction.id)
      toast.push('Transaction deleted.')
      setFilters((current) => ({ ...current }))
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  async function handleImport(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setImporting(true)
    try {
      const result = await api.importTransactions(file)
      const skipped = result.skipped_duplicates ? ` ${result.skipped_duplicates} duplicates skipped.` : ''
      toast.push(`Imported ${result.imported} transactions.${skipped}`, result.errors?.length ? 'info' : 'success')
      if (result.errors?.length) {
        toast.push(`Some rows were skipped: ${result.errors[0].error}`, 'error')
      }
      setFilters((current) => ({ ...current }))
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setImporting(false)
    }
  }

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await api.exportTransactions()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'clearpath-transactions.csv'
      anchor.click()
      URL.revokeObjectURL(url)
      toast.push('Ledger exported as CSV.')
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setExporting(false)
    }
  }

  const pageCount = Math.max(1, Math.ceil(meta.total / meta.per_page))
  const hasFilters = Boolean(filters.q || filters.kind || filters.category)

  return (
    <>
      <PageHeader
        eyebrow="MONEY IN, MONEY OUT"
        title="Transactions"
        description="Every entry is private to your account. Descriptions and notes are encrypted at rest."
        actions={
          <>
            <input ref={fileInput} type="file" accept=".csv,text/csv" hidden onChange={handleImport} />
            <button type="button" className="btn btn-secondary" onClick={() => fileInput.current?.click()} disabled={importing}>
              {importing ? <Spinner /> : <FileUp size={16} />} Import CSV
            </button>
            <button type="button" className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
              {exporting ? <Spinner /> : <Download size={16} />} Export
            </button>
            <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setModalOpen(true) }}>
              <Plus size={16} /> Add transaction
            </button>
          </>
        }
      />

      <div className="ledger-summary-strip">
        <div>
          <span>Ledger entries</span>
          <strong>{meta.total}</strong>
        </div>
        <div>
          <span>Money in</span>
          <strong className="positive">{formatMoney(rows.filter((row) => row.kind === 'income').reduce((sum, row) => sum + Number(row.amount), 0), currency)}</strong>
          <small>on this page</small>
        </div>
        <div>
          <span>Money out</span>
          <strong className="negative">{formatMoney(rows.filter((row) => row.kind === 'expense').reduce((sum, row) => sum + Number(row.amount), 0), currency)}</strong>
          <small>on this page</small>
        </div>
        <div className="strip-note">
          <ArrowDownToLine size={15} />
          <span>
            <strong>CSV import</strong>
            <small>date, kind and amount headers required.</small>
          </span>
        </div>
      </div>

      <Card className="ledger-card">
        <div className="toolbar">
          <label className="search-box">
            <Search size={17} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search description, category or date"
            />
            {query && (
              <button type="button" onClick={() => setQuery('')} aria-label="Clear search">
                <X size={14} />
              </button>
            )}
          </label>
          <select value={filters.kind} onChange={(event) => patchFilters({ kind: event.target.value })} aria-label="Filter by type">
            <option value="">All types</option>
            <option value="expense">Expenses</option>
            <option value="income">Income</option>
          </select>
          <select value={filters.category} onChange={(event) => patchFilters({ category: event.target.value })} aria-label="Filter by category">
            <option value="">All categories</option>
            {ALL_CATEGORIES.map((category) => (
              <option key={category}>{category}</option>
            ))}
          </select>
          {hasFilters && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setQuery(''); setFilters({ q: '', kind: '', category: '', page: 1 }) }}>
              Clear filters
            </button>
          )}
        </div>

        {error ? (
          <EmptyState icon={ReceiptText} title="Could not load the ledger">{error}</EmptyState>
        ) : loading ? (
          <div className="table-loading">
            <Spinner label="Loading transactions…" />
          </div>
        ) : rows.length ? (
          <>
            <div className="table-wrap">
              <table className="data-table ledger-table">
                <thead>
                  <tr>
                    <th>Transaction</th>
                    <th>Category</th>
                    <th>Date</th>
                    <th>Source</th>
                    <th className="right">Amount</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>
                        <div className="tx-name">
                          <span className={`tx-avatar ${transaction.kind}`}>
                            {transaction.kind === 'income' ? <ArrowDownToLine size={15} /> : <ArrowUpFromLine size={15} />}
                          </span>
                          <div>
                            <strong>{transaction.description || transaction.category}</strong>
                            <small>{transaction.notes || titleCase(transaction.kind)}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="category-chip">{transaction.category}</span>
                        {transaction.category_source === 'ml' && (
                          <span className="confidence" title={`Classifier confidence ${Math.round(transaction.category_confidence * 100)}%`}>
                            ML
                          </span>
                        )}
                      </td>
                      <td className="muted-cell">{formatDate(transaction.date)}</td>
                      <td>
                        <Badge tone="neutral">{titleCase(transaction.source)}</Badge>
                      </td>
                      <td className={`right amount-cell ${transaction.kind}`}>
                        {transaction.kind === 'income' ? '+' : '−'}{formatMoney(transaction.amount, currency)}
                      </td>
                      <td>
                        <div className="row-actions">
                          <button type="button" className="icon-btn subtle" onClick={() => { setEditing(transaction); setModalOpen(true) }} aria-label="Edit transaction">
                            <Pencil size={15} />
                          </button>
                          <button type="button" className="icon-btn subtle danger" onClick={() => remove(transaction)} aria-label="Delete transaction">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span>
                Showing {(meta.page - 1) * meta.per_page + 1}–{Math.min(meta.page * meta.per_page, meta.total)} of {meta.total}
              </span>
              <div>
                <button type="button" className="btn btn-secondary btn-sm" disabled={meta.page <= 1} onClick={() => patchFilters({ page: meta.page - 1 })}>
                  <ChevronLeft size={15} /> Previous
                </button>
                <span className="page-indicator">{meta.page} / {pageCount}</span>
                <button type="button" className="btn btn-secondary btn-sm" disabled={!meta.has_more} onClick={() => patchFilters({ page: meta.page + 1 })}>
                  Next <ChevronRight size={15} />
                </button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            icon={ReceiptText}
            title={hasFilters ? 'No transactions match these filters' : 'Your ledger is empty'}
            action={
              <button type="button" className="btn btn-primary btn-sm" onClick={() => { setEditing(null); setModalOpen(true) }}>
                <Plus size={15} /> Add a transaction
              </button>
            }
          >
            {hasFilters ? 'Try clearing the search or choosing another category.' : 'Add an entry manually or import a CSV to get started.'}
          </EmptyState>
        )}
      </Card>

      <div className="csv-note">
        <TrendingUp size={15} />
        <p>
          <strong>Import format:</strong> required columns are <code>date</code>, <code>kind</code> and <code>amount</code>.
          Optional columns are <code>category</code>, <code>description</code>, <code>notes</code> and <code>recurring</code>.
          Invalid rows are rejected with a line number and nothing partial is written for a malformed request.
        </p>
      </div>

      <TransactionModal
        key={editing?.id || 'new'}
        open={modalOpen}
        initial={editing}
        onClose={() => { setModalOpen(false); setEditing(null) }}
        onSaved={() => setFilters((current) => ({ ...current }))}
      />
    </>
  )
}

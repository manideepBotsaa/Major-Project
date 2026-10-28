import { useCallback, useEffect, useState } from 'react'
import {
  ArrowRight,
  Banknote,
  Building2,
  CircleDollarSign,
  Coins,
  Landmark,
  Pencil,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  TrendingUp,
  WalletCards,
} from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { ASSET_TYPES } from '../lib/constants'
import { colorForCategory, formatMoney, formatPct, titleCase } from '../lib/format'
import { ChartTooltip } from '../components/Charts'
import { Badge, Card, EmptyState, Field, Modal, PageHeader, SectionTitle, Spinner, StatCard } from '../components/UI'

const TYPE_ICONS = {
  cash: Banknote,
  investment: TrendingUp,
  retirement: Landmark,
  property: Building2,
  other: Coins,
}

function emptyAsset() {
  return { name: '', asset_type: 'cash', value: '', is_liquid: true }
}

export default function Assets() {
  const { user } = useAuth()
  const toast = useToast()
  const currency = user?.currency || 'INR'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api.assets())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function remove(asset) {
    if (!window.confirm(`Remove “${asset.name}” from your net worth?`)) return
    try {
      await api.deleteAsset(asset.id)
      toast.push('Asset removed.')
      await load()
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  const assets = data?.assets || []
  const net = data?.net_worth
  const groups = (net?.asset_breakdown || []).map((row) => ({ ...row, amount: Number(row.amount) }))
  const byType = ASSET_TYPES.map((type, index) => {
    const rows = assets.filter((asset) => asset.asset_type === type.value)
    return {
      ...type,
      count: rows.length,
      total: rows.reduce((sum, asset) => sum + Number(asset.value), 0),
      color: colorForCategory(type.label, index),
    }
  }).filter((type) => type.count > 0)

  return (
    <>
      <PageHeader
        eyebrow="WHAT YOU OWN, WHAT YOU OWE"
        title="Net worth"
        description="A private balance sheet. Assets are only counted once you record them; debts reduce the total."
        actions={<button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setModalOpen(true) }}><Plus size={16} /> Add asset</button>}
      />

      {loading ? (
        <div className="centered-loader"><Spinner label="Loading your balance sheet…" /></div>
      ) : error ? (
        <Card><EmptyState icon={CircleDollarSign} title="Could not load net worth">{error}</EmptyState></Card>
      ) : (
        <>
          <section className="networth-hero">
            <div>
              <span className="eyebrow light">NET WORTH TODAY</span>
              <strong className={Number(net?.net_worth) < 0 ? 'negative' : ''}>{formatMoney(net?.net_worth, currency)}</strong>
              <p>Assets minus every tracked debt. Liquid money is separated because not all wealth is spendable.</p>
            </div>
            <div className="networth-side">
              <div><span>Total assets</span><strong>{formatMoney(net?.assets, currency)}</strong></div>
              <div><span>Debts</span><strong>{formatMoney(net?.debts, currency)}</strong></div>
              <div><span>Liquid assets</span><strong>{formatMoney(net?.liquid_assets, currency)}</strong></div>
            </div>
          </section>

          <div className="stat-grid four">
            <StatCard label="Cash & bank" value={formatMoney(net?.cash_assets, currency)} icon={Banknote} note="Counts toward the emergency runway" />
            <StatCard label="Liquid wealth" value={formatMoney(net?.liquid_assets, currency)} icon={WalletCards} note={`${assets.filter((asset) => asset.is_liquid).length} liquid entries`} tone="sand" />
            <StatCard label="Assets tracked" value={net?.asset_count ?? 0} icon={CircleDollarSign} note="Property, investments and cash" tone="blue" />
            <StatCard label="Debt balance" value={formatMoney(net?.debts, currency)} icon={Landmark} note={`${net?.debt_count ?? 0} debts`} tone="rose" />
          </div>

          {assets.length === 0 ? (
            <Card>
              <EmptyState icon={CircleDollarSign} title="Your balance sheet is empty" action={<button type="button" className="btn btn-primary btn-sm" onClick={() => setModalOpen(true)}><Plus size={15} /> Add your first asset</button>}>
                Start with cash and bank balances. Add investments and property only when you want the complete picture.
              </EmptyState>
            </Card>
          ) : (
            <div className="dashboard-grid wide-left">
              <Card>
                <SectionTitle title="Asset register" description="Values are what you enter; Clearpath does not connect to a bank or fetch market prices." />
                <div className="asset-list">
                  {assets.map((asset) => {
                    const Icon = TYPE_ICONS[asset.asset_type] || Coins
                    return (
                      <div className="asset-row" key={asset.id}>
                        <span className="asset-icon"><Icon size={17} /></span>
                        <div className="asset-main">
                          <strong>{asset.name}</strong>
                          <small>{ASSET_TYPES.find((type) => type.value === asset.asset_type)?.label || titleCase(asset.asset_type)} · {asset.is_liquid ? 'Liquid' : 'Illiquid'}</small>
                        </div>
                        <strong className="asset-value">{formatMoney(asset.value, currency)}</strong>
                        <div className="row-actions">
                          <button type="button" className="icon-btn" onClick={() => { setEditing(asset); setModalOpen(true) }} aria-label={`Edit ${asset.name}`}><Pencil size={15} /></button>
                          <button type="button" className="icon-btn danger" onClick={() => remove(asset)} aria-label={`Delete ${asset.name}`}><Trash2 size={15} /></button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </Card>

              <div className="stack-column">
                <Card className="chart-card">
                  <SectionTitle title="Asset mix" description="Share of gross assets by type." />
                  <div className="mini-donut">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={groups} dataKey="amount" nameKey="type" innerRadius="66%" outerRadius="92%" paddingAngle={3} stroke="none">
                          {groups.map((row, index) => <Cell key={row.type} fill={colorForCategory(titleCase(row.type), index)} />)}
                        </Pie>
                        <Tooltip content={<ChartTooltip currency={currency} />} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center">
                      <strong>{formatMoney(net?.assets, currency, { compact: true })}</strong>
                      <span>assets</span>
                    </div>
                  </div>
                  <div className="asset-legend">
                    {byType.map((type) => (
                      <div key={type.value}>
                        <i style={{ background: type.color }} />
                        <span>{type.label}</span>
                        <strong>{formatMoney(type.total, currency, { compact: true })}</strong>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="plain-note-card">
                  <ShieldCheck size={20} />
                  <div>
                    <strong>Why cash is separated</strong>
                    <p>
                      Emergency runway is based on cash assets, not total net worth. A house or a locked-in retirement
                      account cannot pay for a medical bill next week.
                    </p>
                  </div>
                </Card>
              </div>
            </div>
          )}

          <Card className="advisor-invite compact-invite">
            <div>
              <span className="eyebrow light">THE WHOLE PICTURE</span>
              <h2>{Number(net?.net_worth) < 0 ? 'Debt is ahead of assets.' : 'Your assets are ahead of debt.'}</h2>
              <p>{Number(net?.net_worth) < 0 ? 'A negative net worth is a starting point, not a verdict. The advisor can sequence the fixes.' : 'Growth matters only after the emergency buffer and expensive debt are under control.'}</p>
            </div>
            <a className="btn btn-dark" href={`/advisor?q=${encodeURIComponent('What should I fix first to improve my financial health?')}`}>
              Ask what to fix <ArrowRight size={14} />
            </a>
          </Card>
        </>
      )}

      <AssetModal open={modalOpen} initial={editing} onClose={() => { setModalOpen(false); setEditing(null) }} onSaved={load} />
    </>
  )
}

function AssetModal({ open, initial, onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(emptyAsset())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(initial ? { name: initial.name, asset_type: initial.asset_type, value: initial.value, is_liquid: Boolean(initial.is_liquid) } : emptyAsset())
  }, [open, initial])

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = { ...form, value: Number(form.value) }
      if (initial) await api.updateAsset(initial.id, payload)
      else await api.createAsset(payload)
      toast.push(initial ? 'Asset updated.' : 'Asset added.')
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
      title={initial ? `Edit ${initial.name}` : 'Add an asset'}
      eyebrow="A FACT, NOT A FEELING"
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" form="asset-form" className="btn btn-primary" disabled={busy}>{busy ? <Spinner label="Saving…" /> : 'Save asset'}</button>
        </>
      }
    >
      <form id="asset-form" className="stack-form" onSubmit={submit}>
        <Field label="Asset name">
          <input required maxLength={120} value={form.name} placeholder="HDFC savings account" onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </Field>
        <div className="form-grid two">
          <Field label="Asset type">
            <select value={form.asset_type} onChange={(event) => setForm({ ...form, asset_type: event.target.value })}>
              {ASSET_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </Field>
          <Field label="Current value">
            <div className="amount-field"><span>₹</span><input type="number" min="0" step="1" required value={form.value} placeholder="150000" onChange={(event) => setForm({ ...form, value: event.target.value })} /></div>
          </Field>
        </div>
        <label className="check-row">
          <input type="checkbox" checked={form.is_liquid} onChange={(event) => setForm({ ...form, is_liquid: event.target.checked })} />
          <span><strong>Liquid asset</strong><small>Can be converted to cash quickly without a material loss. Cash and savings accounts are liquid; property usually is not.</small></span>
        </label>
        {error && <div className="form-error">{error}</div>}
      </form>
    </Modal>
  )
}

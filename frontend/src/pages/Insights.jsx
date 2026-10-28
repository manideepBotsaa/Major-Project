import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  CalendarRange,
  ChartNoAxesCombined,
  CircleDollarSign,
  CreditCard,
  Gauge,
  LineChart as LineChartIcon,
  RefreshCw,
  Repeat2,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  WandSparkles,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { EXPENSE_CATEGORIES } from '../lib/constants'
import { colorForCategory, formatDate, formatMoney, formatMonthKey, formatPct, titleCase } from '../lib/format'
import { ChartLegend, ChartTooltip } from '../components/Charts'
import { Badge, Callout, Card, EmptyState, Field, PageHeader, ProgressBar, SectionTitle, Spinner, StatCard, statusTone } from '../components/UI'

export default function Insights() {
  const { user } = useAuth()
  const toast = useToast()
  const currency = user?.currency || 'INR'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [whatIf, setWhatIf] = useState({ category: 'Food & Dining', reduction_pct: 20, extra_savings: 2000, extra_debt_payment: 0, months: 12 })
  const [whatIfResult, setWhatIfResult] = useState(null)
  const [whatIfBusy, setWhatIfBusy] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const [overview, health, forecast, trends, recurring, anomalies] = await Promise.all([
        api.overview(),
        api.health(),
        api.forecast(3),
        api.trends(6),
        api.recurring(),
        api.anomalies(),
      ])
      setData({ overview, health, forecast, trends, recurring: recurring.recurring, anomalies: anomalies.anomalies })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function runWhatIf(event) {
    event.preventDefault()
    setWhatIfBusy(true)
    try {
      setWhatIfResult(await api.whatIf({ ...whatIf, reduction_pct: Number(whatIf.reduction_pct), extra_savings: Number(whatIf.extra_savings), extra_debt_payment: Number(whatIf.extra_debt_payment), months: Number(whatIf.months) }))
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setWhatIfBusy(false)
    }
  }

  if (loading) return <div className="centered-loader"><Spinner label="Reading your financial picture…" /></div>
  if (error && !data) return <Card><EmptyState icon={Gauge} title="Could not load insights">{error}</EmptyState></Card>
  if (!data) return null

  const { overview, health, forecast, trends, recurring, anomalies } = data
  const month = overview.month
  const cashflow = overview.cashflow.map((row) => ({ ...row, income: Number(row.income), expenses: Number(row.expenses), net: Number(row.net) }))
  const forecastData = [
    ...forecast.history.slice(-8).map((row) => ({ label: row.label, actual: Number(row.amount) })),
    ...forecast.forecast.map((row) => ({ label: row.label, forecast: Number(row.amount), low: Number(row.low), high: Number(row.high) })),
  ]
  const trendCategories = trends.series.slice(0, 4)
  const trendData = trends.months.map((monthRow, index) => {
    const row = { label: monthRow.label }
    trendCategories.forEach((category) => {
      row[category.category] = category.values[index]
    })
    return row
  })
  const safe = overview.safe_to_spend

  return (
    <>
      <PageHeader
        eyebrow="THE ARITHMETIC BEHIND THE ADVICE"
        title="Insights"
        description="Health, forecasts and anomalies are computed from your records. This page shows the working."
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={load}><RefreshCw size={15} /> Refresh</button>
            <a className="btn btn-primary" href="/advisor"><Sparkles size={16} /> Ask why</a>
          </>
        }
      />

      <div className="insight-hero-grid">
        <section className="insight-hero">
          <div>
            <span className="eyebrow light">SAFE TO SPEND · {month.label.toUpperCase()}</span>
            <strong>{formatMoney(safe.amount, currency)}</strong>
            <p>{formatMoney(safe.daily, currency)} per day for {safe.days_left} days. {safe.note}</p>
          </div>
          <div className="insight-hero-side">
            <div><span>Income</span><strong>{formatMoney(month.income, currency)}</strong></div>
            <div><span>Expenses</span><strong>{formatMoney(month.expenses, currency)}</strong></div>
            <div><span>Net</span><strong className={Number(month.net) < 0 ? 'negative' : 'positive'}>{formatMoney(month.net, currency, { signed: true })}</strong></div>
          </div>
        </section>
        <Card className="health-card">
          <SectionTitle title="Financial health" description={`${health.grade} · six weighted components`} action={<Badge tone={health.score >= 65 ? 'green' : health.score >= 45 ? 'amber' : 'red'}>{health.score}/100</Badge>} />
          <div className="health-components">
            {health.components.map((component) => (
              <div key={component.key} className="health-component">
                <div>
                  <span>{component.label}</span>
                  <strong>{component.value}</strong>
                </div>
                <ProgressBar value={component.score} max={component.max} tone={component.status === 'good' ? 'green' : component.status === 'watch' ? 'amber' : 'red'} height={6} />
                <small>{component.score} / {component.max}</small>
              </div>
            ))}
          </div>
          <div className="health-priority"><span>Biggest opportunity</span><strong>{health.top_priority}</strong></div>
        </Card>
      </div>

      <div className="stat-grid four">
        <StatCard label="Emergency runway" value={`${overview.emergency_fund.months_covered} mo`} icon={ShieldCheck} note={`${formatMoney(overview.emergency_fund.cash_available, currency)} in cash`} tone={overview.emergency_fund.status === 'low' ? 'rose' : 'green'} />
        <StatCard label="Net worth" value={formatMoney(overview.net_worth.net_worth, currency)} icon={CircleDollarSign} note={`${overview.net_worth.asset_count} assets · ${overview.net_worth.debt_count} debts`} tone="sand" />
        <StatCard label="Savings rate" value={month.savings_rate == null ? '—' : formatPct(month.savings_rate, 1)} icon={TrendingDown} note="Current month, income less expenses" tone="blue" />
        <StatCard label="Forecast confidence" value={titleCase(forecast.confidence)} icon={LineChartIcon} note={forecast.metrics?.mape != null ? `${forecast.metrics.mape}% holdout MAPE` : 'Not enough data for holdout error'} tone="clay" />
      </div>

      <div className="dashboard-grid wide-left">
        <Card className="chart-card">
          <SectionTitle
            title="Expense forecast"
            description={`${titleCase(forecast.method.replaceAll('_', ' '))} · 80% interval around the central estimate.`}
            action={<Badge tone={forecast.confidence === 'high' ? 'green' : forecast.confidence === 'medium' ? 'amber' : 'neutral'}>{forecast.confidence} confidence</Badge>}
          />
          {forecast.forecast.length ? (
            <>
              <ChartLegend items={[{ label: 'Actual', color: '#315d4b' }, { label: 'Forecast', color: '#c9855f' }]} />
              <div className="chart-lg">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={forecastData} margin={{ top: 10, right: 8, left: -12, bottom: 0 }}>
                    <defs>
                      <linearGradient id="fcBand" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#c9855f" stopOpacity={0.16} />
                        <stop offset="100%" stopColor="#c9855f" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="#edf0eb" />
                    <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                    <Area type="monotone" dataKey="high" stroke="none" fill="url(#fcBand)" />
                    <Area type="monotone" dataKey="actual" stroke="#315d4b" strokeWidth={2.2} fill="none" connectNulls />
                    <Area type="monotone" dataKey="forecast" stroke="#c9855f" strokeWidth={2.2} strokeDasharray="5 4" fill="none" connectNulls />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="forecast-table">
                {forecast.forecast.map((row) => (
                  <div key={row.month}>
                    <span>{row.label}</span>
                    <strong>{formatMoney(row.amount, currency)}</strong>
                    <small>{formatMoney(row.low, currency, { compact: true })}–{formatMoney(row.high, currency, { compact: true })}</small>
                  </div>
                ))}
              </div>
              <p className="model-note">{forecast.note}</p>
            </>
          ) : (
            <EmptyState icon={LineChartIcon} title="Not enough complete months">{forecast.note}</EmptyState>
          )}
        </Card>

        <Card className="chart-card">
          <SectionTitle title="Twelve-month cash flow" description="The same series used on your dashboard." />
          <div className="chart-lg">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cashflow} margin={{ top: 10, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#edf0eb" />
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
                <Tooltip content={<ChartTooltip currency={currency} />} />
                <Bar dataKey="income" name="Income" fill="#315d4b" radius={[4, 4, 0, 0]} maxBarSize={14} />
                <Bar dataKey="expenses" name="Expenses" fill="#c9855f" radius={[4, 4, 0, 0]} maxBarSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card className="chart-card">
          <SectionTitle title="Category trends" description="Six complete months. A flat line can be as informative as a spike." />
          {trendCategories.length ? (
            <div className="chart-md">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#edf0eb" />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} />
                  <Tooltip content={<ChartTooltip currency={currency} />} />
                  {trendCategories.map((category, index) => (
                    <Line key={category.category} type="monotone" dataKey={category.category} name={category.category} stroke={colorForCategory(category.category, index)} strokeWidth={2} dot={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No category history yet" />}
          <ChartLegend items={trendCategories.map((category, index) => ({ label: category.category, color: colorForCategory(category.category, index) }))} />
        </Card>

        <Card>
          <SectionTitle title="Recurring charges" description="Detected from repeated amount and timing, not a bank feed." action={<Repeat2 size={17} />} />
          {recurring.length ? (
            <div className="recurring-list">
              {recurring.slice(0, 6).map((row) => (
                <div key={`${row.merchant}-${row.last_date}`} className="recurring-row">
                  <span className="recurring-avatar">{row.merchant.slice(0, 1).toUpperCase()}</span>
                  <div>
                    <strong>{row.merchant}</strong>
                    <small>{row.category} · next around {formatDate(row.next_expected, 'short')}</small>
                  </div>
                  <div className="recurring-cost">
                    <strong>{formatMoney(row.monthly_cost, currency)}</strong>
                    <small>{formatMoney(row.annual_cost, currency)}/yr</small>
                  </div>
                  <Badge tone={row.days_until <= 3 ? 'amber' : 'neutral'}>{row.days_until < 0 ? 'overdue' : `in ${row.days_until}d`}</Badge>
                </div>
              ))}
            </div>
          ) : <EmptyState icon={Repeat2} title="No recurring charges found">Three or more similar payments about a month apart are needed.</EmptyState>}
        </Card>
      </div>

      <div className="dashboard-grid wide-left">
        <Card className="whatif-card">
          <SectionTitle title="What if?" description="A deterministic counterfactual. Nothing is changed in your ledger." action={<WandSparkles size={18} />} />
          <form className="whatif-form" onSubmit={runWhatIf}>
            <Field label="Category to trim">
              <select value={whatIf.category} onChange={(event) => setWhatIf({ ...whatIf, category: event.target.value })}>
                {EXPENSE_CATEGORIES.map((category) => <option key={category}>{category}</option>)}
              </select>
            </Field>
            <Field label={`Reduce by ${whatIf.reduction_pct}%`}>
              <input type="range" min="0" max="50" step="5" value={whatIf.reduction_pct} onChange={(event) => setWhatIf({ ...whatIf, reduction_pct: event.target.value })} />
            </Field>
            <Field label="Extra monthly savings">
              <div className="amount-field"><span>₹</span><input type="number" min="0" step="500" value={whatIf.extra_savings} onChange={(event) => setWhatIf({ ...whatIf, extra_savings: event.target.value })} /></div>
            </Field>
            <Field label="Extra debt payment">
              <div className="amount-field"><span>₹</span><input type="number" min="0" step="500" value={whatIf.extra_debt_payment} onChange={(event) => setWhatIf({ ...whatIf, extra_debt_payment: event.target.value })} /></div>
            </Field>
            <Field label="Horizon">
              <select value={whatIf.months} onChange={(event) => setWhatIf({ ...whatIf, months: event.target.value })}>
                {[6, 12, 24, 36].map((months) => <option key={months} value={months}>{months} months</option>)}
              </select>
            </Field>
            <button type="submit" className="btn btn-primary" disabled={whatIfBusy}>{whatIfBusy ? <Spinner /> : <Sparkles size={15} />} Run scenario</button>
          </form>

          {whatIfResult && (
            <div className="whatif-result">
              <div className="whatif-summary">
                <div><span>Monthly improvement</span><strong>{formatMoney(whatIfResult.monthly_improvement, currency)}</strong></div>
                <div><span>Extra saved over {whatIfResult.months} months</span><strong>{formatMoney(whatIfResult.extra_savings, currency)}</strong></div>
                <div><span>New monthly savings</span><strong>{formatMoney(whatIfResult.scenario_monthly_savings, currency)}</strong></div>
              </div>
              {whatIfResult.goal_impact && (
                <div className="whatif-detail">
                  <div><span>Goal</span><strong>{whatIfResult.goal_impact.goal}</strong></div>
                  <div><span>One-year projection now</span><strong>{formatMoney(whatIfResult.goal_impact.baseline_value, currency)}</strong></div>
                  <div><span>With this change</span><strong>{formatMoney(whatIfResult.goal_impact.scenario_value, currency)}</strong></div>
                  <div><span>Difference</span><strong className="positive">+{formatMoney(whatIfResult.goal_impact.extra_value, currency)}</strong></div>
                </div>
              )}
              {whatIfResult.debt?.interest_saved != null && (
                <p className="whatif-debt"><CreditCardIcon /> Debt interest saved: <strong>{formatMoney(whatIfResult.debt.interest_saved, currency)}</strong> · months saved: {whatIfResult.debt.months_saved}</p>
              )}
              <p className="model-note">{whatIfResult.assumptions.join(' ')}</p>
            </div>
          )}
        </Card>

        <div className="stack-column">
          <Card>
            <SectionTitle title="Anomalies" description="Unusual for your own pattern, not unusual in general." action={<AlertTriangle size={17} />} />
            {anomalies.length ? (
              <div className="anomaly-list">
                {anomalies.slice(0, 4).map((row) => (
                  <div key={row.transaction.id} className="anomaly-row">
                    <span className={`anomaly-dot ${row.severity}`} />
                    <div>
                      <strong>{row.transaction.description || row.transaction.category}</strong>
                      <small>{formatDate(row.transaction.date, 'short')} · {row.multiple ? `${row.multiple}× typical` : 'above usual'}</small>
                    </div>
                    <strong>{formatMoney(row.transaction.amount, currency)}</strong>
                  </div>
                ))}
              </div>
            ) : <EmptyState icon={ShieldCheck} title="Nothing unusual">No recent expense is far outside your own history.</EmptyState>}
          </Card>
          <Card className="plain-note-card">
            <ChartNoAxesCombined size={20} />
            <div>
              <strong>Forecast model card</strong>
              <p>Ridge regression on three monthly lags, 3- and 6-month rolling means, and month-of-year terms. The last three months are held out. Sparse histories use a moving average.</p>
            </div>
          </Card>
        </div>
      </div>

      <div className="insight-footer-links">
        <a href="/research" className="text-link">See how these models are benchmarked <ArrowRight size={14} /></a>
        <a href="/advisor" className="text-link">Ask the advisor to explain a number <ArrowRight size={14} /></a>
      </div>

      <Card className="advisor-invite compact-invite">
        <div>
          <span className="eyebrow light">THE EXPLANATION LAYER</span>
          <h2>“Where did my money go this month?”</h2>
          <p>The deterministic overview is ready. The advisor adds context and citations without inventing a figure.</p>
        </div>
        <a className="btn btn-dark" href="/advisor">Open advisor <ArrowRight size={14} /></a>
      </Card>
    </>
  )
}

function CreditCardIcon() {
  return <CreditCard size={13} aria-hidden="true" />
}

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  ArrowUpRight,
  BadgeIndianRupee,
  CalendarDays,
  CircleDollarSign,
  Gauge,
  Plus,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { colorForCategory, formatDate, formatMoney, formatPct, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, ErrorState, PageHeader, ProgressBar, SectionTitle, Skeleton, StatCard, statusTone } from '../components/UI'
import { ChartLegend, ChartTooltip } from '../components/Charts'
import AffordabilityChecker from '../components/AffordabilityChecker'
import NudgeCard from '../components/NudgeCard'
import TransactionModal from '../components/TransactionModal'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function HealthRing({ score, grade }) {
  const radius = 47
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference
  return (
    <div className="health-ring-wrap">
      <svg viewBox="0 0 116 116" className="health-ring" aria-label={`Financial health ${score} out of 100`}>
        <circle cx="58" cy="58" r={radius} className="ring-track" />
        <circle
          cx="58"
          cy="58"
          r={radius}
          className="ring-value"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="health-ring-label">
        <strong>{score}</strong>
        <span>/ 100</span>
      </div>
      <Badge tone={score >= 65 ? 'green' : score >= 45 ? 'amber' : 'red'}>{grade}</Badge>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const [overview, transactions] = await Promise.all([
        api.overview(),
        api.transactions({ per_page: 6 }),
      ])
      setData(overview)
      setRecent(transactions.transactions)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <DashboardSkeleton />
  if (error && !data) return <ErrorState message={error} onRetry={load} />
  if (!data) return null

  const currency = user?.currency || 'INR'
  const month = data.month
  const safe = data.safe_to_spend
  const health = data.financial_health
  const goals = data.goals.goals.slice(0, 3)
  const activeNudges = (data.nudges || []).filter((nudge) => nudge.status === 'active')
  const cashflow = data.cashflow.map((row) => ({
    ...row,
    income: Number(row.income),
    expenses: Number(row.expenses),
  }))
  const categories = month.expense_categories.slice(0, 7).map((row) => ({
    ...row,
    value: Number(row.amount),
  }))
  const net = Number(month.net)
  const savingsRate = month.savings_rate

  return (
    <>
      <PageHeader
        eyebrow={`${month.label.toUpperCase()} · YOUR FINANCIAL SNAPSHOT`}
        title={`${greeting()}, ${user?.name?.split(' ')[0] || 'there'}.`}
        description="Here is the honest picture of your money, the arithmetic behind it and the next useful step."
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setModalOpen(true)}>
              <Plus size={16} /> Add transaction
            </button>
            <Link to="/advisor" className="btn btn-primary">
              <Sparkles size={16} /> Ask Clearpath
            </Link>
          </>
        }
      />

      {error && <ErrorState message={error} onRetry={load} />}

      <div className="hero-grid">
        <section className="safe-card">
          <div className="safe-card-copy">
            <span className="eyebrow light">SAFE TO SPEND · REST OF {month.label.split(' ')[0].toUpperCase()}</span>
            <div className="safe-amount">{formatMoney(safe.amount, currency)}</div>
            <p>
              {formatMoney(safe.daily, currency)} per day for {safe.days_left} days. This is a ceiling, not a target.
            </p>
            <div className="safe-basis">
              <ShieldCheck size={15} />
              {safe.basis === 'budget'
                ? 'Based on remaining discretionary budgets, with upcoming subscriptions reserved.'
                : safe.note}
            </div>
          </div>
          <div className="safe-side">
            <div className="safe-mini">
              <span>Emergency runway</span>
              <strong>{data.emergency_fund.months_covered} mo</strong>
              <small>{formatMoney(data.emergency_fund.cash_available, currency)} cash</small>
            </div>
            <div className="safe-mini">
              <span>Net worth</span>
              <strong>{formatMoney(data.net_worth.net_worth, currency, { compact: true })}</strong>
              <small>{data.net_worth.debt_count} debts tracked</small>
            </div>
            <Link to="/insights" className="safe-link">
              See the full reasoning <ArrowUpRight size={14} />
            </Link>
          </div>
        </section>

        <Card className="health-card">
          <SectionTitle title="Financial health" description="Six weighted components, no vanity metric." />
          <HealthRing score={health.score} grade={health.grade} />
          <div className="health-priority">
            <span>Biggest opportunity</span>
            <strong>{health.top_priority}</strong>
          </div>
          <Link to="/insights" className="text-link">
            Break down the score <ArrowRight size={14} />
          </Link>
        </Card>
      </div>

      <div className="stat-grid four">
        <StatCard
          label="Income this month"
          value={formatMoney(month.income, currency)}
          icon={TrendingUp}
          tone="green"
          note={`${month.transaction_count} entries recorded`}
        />
        <StatCard
          label="Expenses this month"
          value={formatMoney(month.expenses, currency)}
          icon={TrendingDown}
          tone="clay"
          note={`${month.expense_categories.length} spending categories`}
        />
        <StatCard
          label="Net cash flow"
          value={formatMoney(month.net, currency, { signed: true })}
          icon={Wallet}
          tone={net >= 0 ? 'sand' : 'rose'}
          note={net >= 0 ? 'Income less expenses' : 'Expenses exceeded income'}
        />
        <StatCard
          label="Savings rate"
          value={savingsRate == null ? '—' : formatPct(savingsRate, 1)}
          icon={BadgeIndianRupee}
          tone="blue"
          note={savingsRate == null ? 'Add income to calculate' : 'Share of income retained'}
        />
      </div>

      <div className="dashboard-grid wide-left">
        <Card className="chart-card">
          <SectionTitle
            title="Twelve-month cash flow"
            description="Income and expenses from your complete recorded history."
            action={<Link to="/insights" className="text-link">Explore <ArrowRight size={14} /></Link>}
          />
          <ChartLegend items={[{ label: 'Income', color: '#315d4b' }, { label: 'Expenses', color: '#c9855f' }]} />
          <div className="chart-lg">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={cashflow} margin={{ top: 10, right: 4, left: -12, bottom: 0 }}>
                <defs>
                  <linearGradient id="incomeFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#315d4b" stopOpacity={0.18} />
                    <stop offset="100%" stopColor="#315d4b" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="expenseFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c9855f" stopOpacity={0.16} />
                    <stop offset="100%" stopColor="#c9855f" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="#edf0eb" />
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#87938c', fontSize: 11 }}
                  tickFormatter={(value) => `${Math.round(value / 1000)}k`}
                />
                <Tooltip content={<ChartTooltip currency={currency} />} />
                <Area type="monotone" dataKey="income" name="Income" stroke="#315d4b" strokeWidth={2} fill="url(#incomeFill)" />
                <Area type="monotone" dataKey="expenses" name="Expenses" stroke="#c9855f" strokeWidth={2} fill="url(#expenseFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="affordability-card">
          <SectionTitle
            title="Can I afford it?"
            description="A just-in-time check, computed before you spend."
          />
          <AffordabilityChecker currency={currency} compact />
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card className="chart-card">
          <SectionTitle
            title="Where the money went"
            description={`${month.label} expenses by category.`}
            action={<span className="period-chip">{formatMoney(month.expenses, currency)}</span>}
          />
          {categories.length ? (
            <div className="donut-layout">
              <div className="donut-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categories}
                      dataKey="value"
                      nameKey="category"
                      innerRadius="66%"
                      outerRadius="90%"
                      paddingAngle={3}
                      stroke="none"
                    >
                      {categories.map((category, index) => (
                        <Cell key={category.category} fill={colorForCategory(category.category, index)} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip currency={currency} />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center">
                  <strong>{formatMoney(month.expenses, currency, { compact: true })}</strong>
                  <span>spent</span>
                </div>
              </div>
              <div className="category-legend">
                {categories.map((category) => (
                  <div key={category.category} className="category-row">
                    <i style={{ background: colorForCategory(category.category) }} />
                    <span>{category.category}</span>
                    <small>{formatPct(category.share, 0)}</small>
                    <strong>{formatMoney(category.amount, currency)}</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState icon={ReceiptText} title="No spending recorded this month">
              Add a transaction and the category picture will appear here.
            </EmptyState>
          )}
        </Card>

        <Card className="goals-mini-card">
          <SectionTitle
            title="Goals"
            description={`${data.goals.on_track_count} on track · ${data.goals.at_risk_count} need attention`}
            action={<Link to="/goals" className="text-link">All goals <ArrowRight size={14} /></Link>}
          />
          {goals.length ? (
            <div className="goal-mini-list">
              {goals.map((goal) => (
                <Link to="/goals" key={goal.id} className="goal-mini">
                  <div className="goal-mini-top">
                    <span className="goal-icon">
                      <Target size={15} />
                    </span>
                    <div>
                      <strong>{goal.name}</strong>
                      <small>
                        {formatMoney(goal.saved_amount, currency)} of {formatMoney(goal.target_amount, currency)}
                      </small>
                    </div>
                    <Badge tone={statusTone(goal.status)}>{titleCase(goal.status)}</Badge>
                  </div>
                  <ProgressBar value={goal.progress_pct} tone={goal.status === 'off_track' ? 'red' : goal.status === 'at_risk' ? 'amber' : 'green'} />
                  <div className="goal-mini-foot">
                    <span>{formatPct(goal.progress_pct, 0)} complete</span>
                    <span>{goal.probability == null ? 'No deadline' : `${Math.round(goal.probability * 100)}% success est.`}</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState icon={Target} title="No goals yet">
              A goal gives each spending decision a reference point.
              <Link to="/goals" className="text-link">Create your first goal <ArrowRight size={14} /></Link>
            </EmptyState>
          )}
        </Card>
      </div>

      <section className="section-block">
        <SectionTitle
          title="Just-in-time nudges"
          description="Generated from this month's arithmetic, not generic tips."
          action={<Link to="/momentum" className="text-link">All nudges <ArrowRight size={14} /></Link>}
        />
        {activeNudges.length ? (
          <div className="nudge-grid">
            {activeNudges.slice(0, 2).map((nudge) => (
              <NudgeCard key={nudge.id} nudge={nudge} onChanged={load} compact />
            ))}
          </div>
        ) : (
          <Card>
            <EmptyState icon={ShieldCheck} title="No urgent nudges">
              Nothing needs intervention right now. That is a result worth protecting.
            </EmptyState>
          </Card>
        )}
      </section>

      <Card className="recent-card">
        <SectionTitle
          title="Recent activity"
          description="The latest entries across all accounts and categories."
          action={<Link to="/transactions" className="text-link">View ledger <ArrowRight size={14} /></Link>}
        />
        {recent.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Category</th>
                  <th>Date</th>
                  <th className="right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((transaction) => (
                  <tr key={transaction.id}>
                    <td>
                      <div className="tx-name">
                        <span className={`tx-avatar ${transaction.kind}`}>
                          {transaction.kind === 'income' ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
                        </span>
                        <div>
                          <strong>{transaction.description || transaction.category}</strong>
                          <small>{titleCase(transaction.source)} · {transaction.category_source}</small>
                        </div>
                      </div>
                    </td>
                    <td><span className="category-chip">{transaction.category}</span></td>
                    <td className="muted-cell">{formatDate(transaction.date, 'short')}</td>
                    <td className={`right amount-cell ${transaction.kind}`}>
                      {transaction.kind === 'income' ? '+' : '−'}{formatMoney(transaction.amount, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon={ReceiptText} title="Your ledger is empty">
            Add the first transaction to make the dashboard come alive.
          </EmptyState>
        )}
      </Card>

      <TransactionModal open={modalOpen} initial={null} onClose={() => setModalOpen(false)} onSaved={load} />
    </>
  )
}

function DashboardSkeleton() {
  return (
    <>
      <div className="page-header">
        <div>
          <Skeleton className="skeleton-eyebrow" />
          <Skeleton className="skeleton-title" />
          <Skeleton className="skeleton-text" />
        </div>
      </div>
      <div className="hero-grid">
        <Skeleton className="skeleton-hero" />
        <Skeleton className="skeleton-hero-small" />
      </div>
      <div className="stat-grid four">
        {[0, 1, 2, 3].map((item) => <Skeleton key={item} className="skeleton-stat" />)}
      </div>
      <div className="dashboard-grid wide-left">
        <Skeleton className="skeleton-chart" />
        <Skeleton className="skeleton-chart" />
      </div>
    </>
  )
}

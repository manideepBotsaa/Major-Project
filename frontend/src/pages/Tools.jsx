import { useMemo, useState } from 'react'
import {
  ArrowRight,
  Calculator,
  CalendarClock,
  CircleDollarSign,
  Landmark,
  PiggyBank,
  ReceiptText,
  RefreshCw,
  ShieldCheck,
  Sparkles,
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
import { formatMoney, formatPct } from '../lib/format'
import { ChartTooltip } from '../components/Charts'
import { Badge, Card, Field, PageHeader, SectionTitle, Spinner, StatCard, Tabs } from '../components/UI'

const TABS = [
  { id: 'emi', label: 'Loan EMI' },
  { id: 'sip', label: 'SIP' },
  { id: 'swp', label: 'SWP' },
  { id: 'fire', label: 'FIRE' },
  { id: 'compound', label: 'Compound interest' },
]

const DEFAULTS = {
  emi: { principal: 500000, annual_rate: 10.5, months: 60 },
  sip: { monthly_investment: 10000, annual_return: 12, years: 10, step_up_pct: 0 },
  swp: { corpus: 5000000, monthly_withdrawal: 30000, annual_return: 8 },
  fire: { current_age: 30, annual_expenses: 600000, current_savings: 500000, monthly_savings: 25000, annual_return: 9, inflation: 5, withdrawal_rate: 4 },
  compound: { principal: 100000, annual_rate: 8, years: 10, compounds_per_year: 12 },
}

export default function Tools() {
  const { user } = useAuth()
  const toast = useToast()
  const currency = user?.currency || 'INR'
  const [tab, setTab] = useState('emi')
  const [forms, setForms] = useState(DEFAULTS)
  const [results, setResults] = useState({})
  const [busy, setBusy] = useState(false)

  function setField(key, value) {
    setForms((current) => ({ ...current, [tab]: { ...current[tab], [key]: value } }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const payload = Object.fromEntries(Object.entries(forms[tab]).map(([key, value]) => [key, Number(value)]))
      const result = await api[tab](payload)
      setResults((current) => ({ ...current, [tab]: result }))
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const result = results[tab]

  return (
    <>
      <PageHeader
        eyebrow="THE ARITHMETIC BEFORE THE DECISION"
        title="Calculators"
        description="Run the same pure functions the advisor uses. Change an assumption and watch the answer move."
        actions={<a href="/advisor" className="btn btn-primary"><Sparkles size={16} /> Ask what it means</a>}
      />

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="calculator-tabs" />

      <div className="calculator-layout">
        <Card className="calculator-form-card">
          <SectionTitle
            title={TABS.find((item) => item.id === tab).label}
            description={DESCRIPTIONS[tab]}
            action={<Calculator size={18} />}
          />
          <form className="stack-form calculator-form" onSubmit={submit}>
            {FIELDS[tab].map((field) => (
              <Field key={field.key} label={field.label} hint={field.hint}>
                <div className={field.suffix === '₹' || field.suffix === '%' ? 'amount-field' : ''}>
                  {field.suffix && <span>{field.suffix}</span>}
                  <input
                    type="number"
                    min={field.min ?? 0}
                    max={field.max}
                    step={field.step ?? 1}
                    required
                    value={forms[tab][field.key]}
                    onChange={(event) => setField(field.key, event.target.value)}
                  />
                  {field.after && <em>{field.after}</em>}
                </div>
              </Field>
            ))}
            {tab === 'emi' && (
              <div className="preset-row">
                {[12, 24, 36, 60, 84, 120, 240, 360].map((months) => (
                  <button key={months} type="button" className={Number(forms.emi.months) === months ? 'active' : ''} onClick={() => setField('months', months)}>
                    {months >= 12 ? `${months / 12}y` : `${months}m`}
                  </button>
                ))}
              </div>
            )}
            <button type="submit" className="btn btn-primary btn-lg" disabled={busy}>
              {busy ? <Spinner label="Calculating…" /> : <RefreshCw size={16} />} Calculate
            </button>
          </form>
          <div className="calculator-note">
            <ShieldCheck size={14} />
            <span>Calculations run on the deterministic engine. Nothing is stored or shared.</span>
          </div>
        </Card>

        <div className="calculator-results">
          {!result ? (
            <Card className="calculator-placeholder">
              <span className="placeholder-icon"><Calculator size={25} /></span>
              <h2>Your result will appear here.</h2>
              <p>Set the assumptions on the left and calculate. The defaults are illustrative, not recommendations.</p>
              <div className="placeholder-formula">
                <span>EMI</span>
                <code>P × r × (1+r)ⁿ / ((1+r)ⁿ − 1)</code>
              </div>
            </Card>
          ) : tab === 'emi' ? (
            <EmiResult result={result} currency={currency} />
          ) : tab === 'sip' ? (
            <SipResult result={result} currency={currency} />
          ) : tab === 'swp' ? (
            <SwpResult result={result} currency={currency} />
          ) : tab === 'fire' ? (
            <FireResult result={result} currency={currency} />
          ) : (
            <CompoundResult result={result} currency={currency} />
          )}
        </div>
      </div>

      <div className="calculator-explainer-grid">
        <Card className="plain-note-card">
          <PiggyBank size={20} />
          <div>
            <strong>Assumptions are the whole argument</strong>
            <p>A 12% return is not a law of nature. Change it to 8% and the same SIP looks materially smaller. The calculator exposes the assumption instead of hiding it in a headline.</p>
          </div>
        </Card>
        <Card className="plain-note-card">
          <ReceiptText size={20} />
          <div>
            <strong>Not investment advice</strong>
            <p>These tools model arithmetic. They do not account for taxes, exit loads, insurance, liquidity needs or the possibility that you stop contributing.</p>
          </div>
        </Card>
      </div>
    </>
  )
}

const DESCRIPTIONS = {
  emi: 'Monthly payment, total interest and a month-by-month amortisation schedule.',
  sip: 'Future value of a monthly investment, with an optional annual step-up.',
  swp: 'How long a corpus lasts under a fixed monthly withdrawal and a constant return.',
  fire: 'A retirement number and an estimated age, using real return after inflation.',
  compound: 'The effect of compounding frequency on a lump sum.',
}

const FIELDS = {
  emi: [
    { key: 'principal', label: 'Loan amount', suffix: '₹', step: 1000 },
    { key: 'annual_rate', label: 'Annual interest rate', suffix: '%', step: 0.1, max: 60 },
    { key: 'months', label: 'Tenure in months', suffix: '', step: 1, max: 480 },
  ],
  sip: [
    { key: 'monthly_investment', label: 'Monthly investment', suffix: '₹', step: 500 },
    { key: 'annual_return', label: 'Expected annual return', suffix: '%', step: 0.5, max: 30 },
    { key: 'years', label: 'Investment horizon', suffix: '', step: 1, max: 50, after: 'years' },
    { key: 'step_up_pct', label: 'Annual step-up', suffix: '%', step: 1, max: 50, hint: 'Optional. Increase the monthly amount each year.' },
  ],
  swp: [
    { key: 'corpus', label: 'Starting corpus', suffix: '₹', step: 10000 },
    { key: 'monthly_withdrawal', label: 'Monthly withdrawal', suffix: '₹', step: 1000 },
    { key: 'annual_return', label: 'Expected annual return', suffix: '%', step: 0.5, max: 30 },
  ],
  fire: [
    { key: 'current_age', label: 'Current age', suffix: '', step: 1, min: 15, max: 100 },
    { key: 'annual_expenses', label: 'Annual expenses today', suffix: '₹', step: 10000, hint: 'Pre-filled from your recorded spending.' },
    { key: 'current_savings', label: 'Current investments', suffix: '₹', step: 10000, hint: 'Pre-filled from your liquid assets.' },
    { key: 'monthly_savings', label: 'Monthly savings', suffix: '₹', step: 1000 },
    { key: 'annual_return', label: 'Expected nominal return', suffix: '%', step: 0.5, max: 30 },
    { key: 'inflation', label: 'Expected inflation', suffix: '%', step: 0.5, max: 20 },
    { key: 'withdrawal_rate', label: 'Safe withdrawal rate', suffix: '%', step: 0.1, max: 10 },
  ],
  compound: [
    { key: 'principal', label: 'Principal', suffix: '₹', step: 1000 },
    { key: 'annual_rate', label: 'Annual rate', suffix: '%', step: 0.1, max: 50 },
    { key: 'years', label: 'Years', suffix: '', step: 1, max: 60, after: 'years' },
    { key: 'compounds_per_year', label: 'Compounds per year', suffix: '', step: 1, min: 1, max: 365 },
  ],
}

function EmiResult({ result, currency }) {
  const split = [
    { name: 'Principal', value: Number(result.principal), color: '#315d4b' },
    { name: 'Interest', value: Number(result.total_interest), color: '#c9855f' },
  ]
  return (
    <>
      <div className="result-hero">
        <div>
          <span className="eyebrow light">MONTHLY PAYMENT</span>
          <strong>{formatMoney(result.monthly_payment, currency)}</strong>
          <p>{result.months} months at {formatPct(result.annual_rate, 1)} per year.</p>
        </div>
        <div className="result-hero-mini">
          <div><span>Total interest</span><strong>{formatMoney(result.total_interest, currency)}</strong></div>
          <div><span>Total payment</span><strong>{formatMoney(result.total_payment, currency)}</strong></div>
        </div>
      </div>
      <div className="result-grid">
        <Card className="chart-card">
          <SectionTitle title="Principal vs interest" description="Where your total payment goes." />
          <div className="result-donut">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={split} dataKey="value" innerRadius="64%" outerRadius="90%" paddingAngle={3} stroke="none">
                  {split.map((row) => <Cell key={row.name} fill={row.color} />)}
                </Pie>
                <Tooltip content={<ChartTooltip currency={currency} />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center"><strong>{formatPct((Number(result.total_interest) / Number(result.principal)) * 100, 0)}</strong><span>of principal</span></div>
          </div>
          <div className="split-legend">
            {split.map((row) => <span key={row.name}><i style={{ background: row.color }} />{row.name} <strong>{formatMoney(row.value, currency)}</strong></span>)}
          </div>
        </Card>
        <Card className="chart-card">
          <SectionTitle title="Balance over time" description="Principal falls slowly at first because interest is front-loaded." />
          <div className="chart-md">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={result.schedule} margin={{ top: 10, right: 8, left: -16, bottom: 0 }}>
                <defs><linearGradient id="emiFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#315d4b" stopOpacity={0.2} /><stop offset="100%" stopColor="#315d4b" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid vertical={false} stroke="#edf0eb" />
                <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 10 }} tickFormatter={(v) => (v % 12 === 0 ? `${v / 12}y` : '')} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 10 }} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <Tooltip content={<ChartTooltip currency={currency} />} />
                <Area type="monotone" dataKey="balance" name="Balance" stroke="#315d4b" strokeWidth={2} fill="url(#emiFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <Card className="schedule-table-card">
        <SectionTitle title="First 12 payments" description="A shorter tenure usually saves more interest than a marginally lower rate." />
        <div className="table-wrap">
          <table className="data-table compact">
            <thead><tr><th>Month</th><th className="right">Payment</th><th className="right">Principal</th><th className="right">Interest</th><th className="right">Balance</th></tr></thead>
            <tbody>
              {result.schedule.slice(0, 12).map((row) => (
                <tr key={row.month}><td>Month {row.month}</td><td className="right">{formatMoney(row.payment, currency)}</td><td className="right">{formatMoney(row.principal, currency)}</td><td className="right">{formatMoney(row.interest, currency)}</td><td className="right">{formatMoney(row.balance, currency)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

function SipResult({ result, currency }) {
  return (
    <>
      <div className="result-hero">
        <div>
          <span className="eyebrow light">PROJECTED CORPUS</span>
          <strong>{formatMoney(result.future_value, currency)}</strong>
          <p>{formatMoney(result.monthly_investment, currency)}/month for {result.years} years at {formatPct(result.annual_return, 1)}.</p>
        </div>
        <div className="result-hero-mini">
          <div><span>Invested</span><strong>{formatMoney(result.invested, currency)}</strong></div>
          <div><span>Gains</span><strong>{formatMoney(result.gains, currency)}</strong></div>
        </div>
      </div>
      <Card className="chart-card">
        <SectionTitle title="Invested vs value" description="The gap widens because returns compound on prior returns." />
        <div className="chart-lg">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={result.schedule} margin={{ top: 10, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="sipValue" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#315d4b" stopOpacity={0.2} /><stop offset="100%" stopColor="#315d4b" stopOpacity={0} /></linearGradient>
                <linearGradient id="sipInvested" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d0a45c" stopOpacity={0.16} /><stop offset="100%" stopColor="#d0a45c" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="#edf0eb" />
              <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(v) => `${v}y`} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 100000)}L`} />
              <Tooltip content={<ChartTooltip currency={currency} />} />
              <Area type="monotone" dataKey="value" name="Projected value" stroke="#315d4b" strokeWidth={2.2} fill="url(#sipValue)" />
              <Area type="monotone" dataKey="invested" name="Invested" stroke="#d0a45c" strokeWidth={1.8} fill="url(#sipInvested)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <ResultInsight>
        Of the projected {formatMoney(result.future_value, currency)}, {formatMoney(result.gains, currency)} comes from returns, not contributions. A lower return assumption would reduce that share materially.
      </ResultInsight>
    </>
  )
}

function SwpResult({ result, currency }) {
  return (
    <>
      <div className="result-hero">
        <div>
          <span className="eyebrow light">CORPUS LONGEVITY</span>
          <strong>{result.months_lasted >= 1200 ? '100+ years' : `${result.years_lasted} years`}</strong>
          <p>{formatMoney(result.monthly_withdrawal, currency)}/month from {formatMoney(result.corpus, currency)} at {formatPct(result.annual_return, 1)}.</p>
        </div>
        <div className="result-hero-mini">
          <div><span>Months lasted</span><strong>{result.months_lasted}</strong></div>
          <div><span>Total withdrawn</span><strong>{formatMoney(result.total_withdrawn, currency)}</strong></div>
        </div>
      </div>
      <Card className="chart-card">
        <SectionTitle title="Corpus depletion" description="Sequence of returns matters in real life; this model holds the return constant." />
        {result.schedule.length ? (
          <div className="chart-lg">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={result.schedule} margin={{ top: 10, right: 8, left: -12, bottom: 0 }}>
                <defs><linearGradient id="swpFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c9855f" stopOpacity={0.2} /><stop offset="100%" stopColor="#c9855f" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid vertical={false} stroke="#edf0eb" />
                <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(v) => `${v}y`} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#87938c', fontSize: 11 }} tickFormatter={(v) => `${Math.round(v / 100000)}L`} />
                <Tooltip content={<ChartTooltip currency={currency} />} />
                <Area type="monotone" dataKey="balance" name="Balance" stroke="#c9855f" strokeWidth={2.2} fill="url(#swpFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : <p className="model-note">Withdrawal exceeds the return, so the corpus is exhausted in the first month.</p>}
      </Card>
      <ResultInsight>
        A 4% withdrawal rule is a planning heuristic, not a guarantee. A market fall early in retirement can make a portfolio last far less time than a constant-return model suggests.
      </ResultInsight>
    </>
  )
}

function FireResult({ result, currency }) {
  return (
    <>
      <div className="result-hero">
        <div>
          <span className="eyebrow light">FINANCIAL INDEPENDENCE</span>
          <strong>{result.reached ? `${result.years_to_fi} years` : 'Not within 70 years'}</strong>
          <p>{result.reached ? `At this rate, you reach the target around age ${result.fi_age}.` : 'Increase monthly savings or reduce the target to change the trajectory.'}</p>
        </div>
        <div className="result-hero-mini">
          <div><span>FI number today</span><strong>{formatMoney(result.fi_number_today, currency)}</strong></div>
          <div><span>Projected target</span><strong>{formatMoney(result.projected_fi_number, currency)}</strong></div>
        </div>
      </div>
      <div className="result-grid">
        <Card>
          <SectionTitle title="The three numbers" description="Each is doing a different job." />
          <div className="fire-metrics">
            <div><span>Annual expenses</span><strong>{formatMoney(result.annual_expenses, currency)}</strong><small>Today's spending</small></div>
            <div><span>Withdrawal rate</span><strong>{formatPct(result.withdrawal_rate, 1)}</strong><small>Assumed safe rate</small></div>
            <div><span>Real return</span><strong>{formatPct(result.real_return, 2)}</strong><small>After inflation</small></div>
            <div><span>Monthly savings</span><strong>{formatMoney(result.monthly_savings, currency)}</strong><small>Held constant</small></div>
          </div>
        </Card>
        <Card>
          <SectionTitle title="What the result really says" description="The uncertainty is in the assumptions." />
          <ul className="interpretation-list">
            <li><TrendingUp size={15} /><span>A 1% lower return can add years to the timeline. Test it.</span></li>
            <li><CalendarClock size={15} /><span>Inflation raises the target while the projection runs. This model already accounts for it.</span></li>
            <li><ShieldCheck size={15} /><span>FIRE is not only about a number. Health cover, family obligations and liquidity matter.</span></li>
          </ul>
        </Card>
      </div>
      <ResultInsight>
        The FI number is annual expenses divided by the withdrawal rate. The projected number grows with inflation. Reaching one number does not automatically make a plan safe.
      </ResultInsight>
    </>
  )
}

function CompoundResult({ result, currency }) {
  return (
    <>
      <div className="result-hero">
        <div>
          <span className="eyebrow light">COMPOUNDED VALUE</span>
          <strong>{formatMoney(result.amount, currency)}</strong>
          <p>From {formatMoney(result.principal, currency)} principal. Effective annual rate: {formatPct(result.effective_annual_rate, 2)}.</p>
        </div>
        <div className="result-hero-mini">
          <div><span>Principal</span><strong>{formatMoney(result.principal, currency)}</strong></div>
          <div><span>Interest earned</span><strong>{formatMoney(result.interest, currency)}</strong></div>
        </div>
      </div>
      <div className="result-grid">
        <Card><SectionTitle title="What changed" description="Compounding frequency has a modest effect at ordinary rates." /><div className="fire-metrics two"><div><span>Principal</span><strong>{formatMoney(result.principal, currency)}</strong></div><div><span>Total value</span><strong>{formatMoney(result.amount, currency)}</strong></div><div><span>Interest</span><strong>{formatMoney(result.interest, currency)}</strong></div><div><span>Effective annual</span><strong>{formatPct(result.effective_annual_rate, 2)}</strong></div></div></Card>
        <Card><SectionTitle title="The honest caveat" description="" /><ul className="interpretation-list"><li><Landmark size={15} /><span>Taxes are ignored. For many Indian instruments, post-tax returns are materially lower.</span></li><li><CircleDollarSign size={15} /><span>A constant rate is a teaching device, not a market forecast.</span></li></ul></Card>
      </div>
    </>
  )
}

function ResultInsight({ children }) {
  return (
    <div className="result-insight">
      <Sparkles size={16} />
      <p>{children}</p>
      <a href="/advisor" className="text-link">Discuss <ArrowRight size={13} /></a>
    </div>
  )
}

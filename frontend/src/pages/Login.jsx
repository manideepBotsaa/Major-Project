import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  BarChart3,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Spinner } from '../components/UI'

const POINTS = [
  { icon: BarChart3, title: 'One truthful picture', text: 'Cash flow, budgets, goals and debt in a single deterministic engine.' },
  { icon: ShieldCheck, title: 'No invented numbers', text: 'The advisor can explain, but every figure is computed and verified.' },
  { icon: Sparkles, title: 'Help at the decision', text: 'Affordability checks and nudges arrive when the money decision happens.' },
]

export default function Login() {
  const { user, loading, login, register, demoLogin } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="mark mark-pulse">c</div>
        <Spinner label="Opening your workspace…" />
      </div>
    )
  }
  if (user) return <Navigate to="/" replace />

  async function submit(event) {
    event.preventDefault()
    setBusy('form')
    setError('')
    try {
      if (mode === 'login') await login({ email: form.email, password: form.password })
      else await register(form)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  async function enterDemo() {
    setBusy('demo')
    setError('')
    try {
      await demoLogin()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="auth-story-inner">
          <div className="brand auth-brand">
            <span className="brand-mark">c</span>
            <span>clearpath</span>
          </div>
          <div className="auth-story-copy">
            <span className="eyebrow light">GROUNDED PERSONAL FINANCE</span>
            <h1>Clarity for the money decisions you actually make.</h1>
            <p>
              Clearpath combines a deterministic financial engine, just-in-time education and a
              verification-first advisor. It is built for real life in rupees, not market hype.
            </p>
            <div className="auth-points">
              {POINTS.map(({ icon: Icon, title, text }) => (
                <div key={title} className="auth-point">
                  <span>
                    <Icon size={18} />
                  </span>
                  <div>
                    <strong>{title}</strong>
                    <p>{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="auth-proof">
            <span className="proof-line" />
            <p>
              <strong>GroundedPath</strong> · A research system for verifiable, just-in-time financial guidance
            </p>
          </div>
        </div>
      </section>

      <section className="auth-form-side">
        <div className="auth-card">
          <div className="auth-heading">
            <span className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : 'BEGIN HERE'}</span>
            <h2>{mode === 'login' ? 'Pick up where you left off.' : 'Build a clearer money picture.'}</h2>
            <p>
              {mode === 'login'
                ? 'Sign in to your private workspace.'
                : 'Create a local-first account. No bank connection is required.'}
            </p>
          </div>

          <div className="auth-tabs">
            <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>
              Sign in
            </button>
            <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>
              Create account
            </button>
          </div>

          <form className="stack-form" onSubmit={submit}>
            {mode === 'register' && (
              <label className="input-wrap">
                <UserRound size={17} />
                <input
                  required
                  maxLength={100}
                  placeholder="Your name"
                  autoComplete="name"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </label>
            )}
            <label className="input-wrap">
              <Mail size={17} />
              <input
                type="email"
                required
                placeholder="Email address"
                autoComplete="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </label>
            <label className="input-wrap">
              <LockKeyhole size={17} />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                minLength={mode === 'register' ? 10 : undefined}
                placeholder="Password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
              />
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label="Toggle password visibility">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </label>
            {mode === 'register' && (
              <p className="form-hint">
                <Check size={13} /> At least 10 characters, including a letter and a number.
              </p>
            )}
            {error && <div className="form-error">{error}</div>}
            <button type="submit" className="btn btn-primary btn-lg wide" disabled={Boolean(busy)}>
              {busy === 'form' ? <Spinner label="Please wait…" /> : mode === 'login' ? 'Sign in securely' : 'Create my workspace'}
              {!busy && <ArrowRight size={17} />}
            </button>
          </form>

          <div className="auth-divider">
            <span>or explore the research demo</span>
          </div>

          <button type="button" className="btn btn-secondary btn-lg wide demo-btn" onClick={enterDemo} disabled={Boolean(busy)}>
            {busy === 'demo' ? <Spinner label="Preparing 18 months of data…" /> : 'Open the demo workspace'}
          </button>
          <p className="auth-demo-note">
            Demo: 684 transactions, 18 months of history, four goals and three debts. Fully offline.
          </p>

          <p className="auth-legal">
            Clearpath is an educational planning tool, not a SEBI-registered investment adviser or a lender.
            Your records stay in your local database unless you explicitly configure an external model provider.
          </p>
        </div>
      </section>
    </main>
  )
}

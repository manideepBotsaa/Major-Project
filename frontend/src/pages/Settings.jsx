import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  Database,
  Download,
  KeyRound,
  Landmark,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
} from 'lucide-react'
import { api, base } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { formatDate } from '../lib/format'
import { Badge, Callout, Card, Field, PageHeader, SectionTitle, Spinner } from '../components/UI'

const CURRENCIES = [
  { value: 'INR', label: 'Indian rupee (₹)' },
  { value: 'USD', label: 'US dollar ($)' },
  { value: 'EUR', label: 'Euro (€)' },
  { value: 'GBP', label: 'Pound sterling (£)' },
]

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'हिन्दी (Hindi)' },
  { value: 'te', label: 'తెలుగు (Telugu)' },
]

export default function Settings() {
  const { user, updateUser, logout } = useAuth()
  const toast = useToast()
  const [profile, setProfile] = useState({ name: '', currency: 'INR', language: 'en', risk_profile: 'moderate', monthly_income: '' })
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [password, setPassword] = useState({ current_password: '', new_password: '', confirm: '' })
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [advisor, setAdvisor] = useState(null)

  useEffect(() => {
    if (!user) return
    setProfile({
      name: user.name || '',
      currency: user.currency || 'INR',
      language: user.language || 'en',
      risk_profile: user.risk_profile || 'moderate',
      monthly_income: user.monthly_income || '',
    })
  }, [user])

  useEffect(() => {
    api.advisorStatus().then((data) => setAdvisor(data.llm)).catch(() => {})
  }, [])

  async function saveProfile(event) {
    event.preventDefault()
    setProfileBusy(true)
    setProfileError('')
    try {
      const data = await api.updateProfile({ ...profile, monthly_income: profile.monthly_income === '' ? null : Number(profile.monthly_income) })
      updateUser(data.user)
      toast.push('Profile updated.')
    } catch (err) {
      setProfileError(err.message)
    } finally {
      setProfileBusy(false)
    }
  }

  async function savePassword(event) {
    event.preventDefault()
    if (password.new_password !== password.confirm) {
      setPasswordError('The new passwords do not match.')
      return
    }
    setPasswordBusy(true)
    setPasswordError('')
    try {
      await api.changePassword({ current_password: password.current_password, new_password: password.new_password })
      setPassword({ current_password: '', new_password: '', confirm: '' })
      toast.push('Password changed.')
    } catch (err) {
      setPasswordError(err.message)
    } finally {
      setPasswordBusy(false)
    }
  }

  async function exportData() {
    setExporting(true)
    try {
      const data = await api.exportAccount()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'clearpath-account-export.json'
      anchor.click()
      URL.revokeObjectURL(url)
      toast.push('Account export downloaded.')
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setExporting(false)
    }
  }

  async function deleteAccount(event) {
    event.preventDefault()
    setDeleting(true)
    setDeleteError('')
    try {
      await api.deleteAccount(deletePassword)
      toast.push('Account deleted.', 'info')
      await logout()
    } catch (err) {
      setDeleteError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  if (!user) return null

  return (
    <>
      <PageHeader
        eyebrow="YOUR WORKSPACE, YOUR RULES"
        title="Settings"
        description="Profile, security and data controls. Clearpath is local-first: records stay in your own database."
      />

      <div className="settings-grid">
        <Card>
          <SectionTitle title="Profile" description="These settings change formatting and advisor context." action={<UserRound size={18} />} />
          <form className="stack-form" onSubmit={saveProfile}>
            <Field label="Name">
              <input required maxLength={100} value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} />
            </Field>
            <div className="form-grid two">
              <Field label="Currency" hint="Used for display across the app.">
                <select value={profile.currency} onChange={(event) => setProfile({ ...profile, currency: event.target.value })}>
                  {CURRENCIES.map((currency) => <option key={currency.value} value={currency.value}>{currency.label}</option>)}
                </select>
              </Field>
              <Field label="Language" hint="Interface language support is being expanded.">
                <select value={profile.language} onChange={(event) => setProfile({ ...profile, language: event.target.value })}>
                  {LANGUAGES.map((language) => <option key={language.value} value={language.value}>{language.label}</option>)}
                </select>
              </Field>
              <Field label="Risk profile" hint="Frames educational explanations; never a product recommendation.">
                <select value={profile.risk_profile} onChange={(event) => setProfile({ ...profile, risk_profile: event.target.value })}>
                  <option value="conservative">Conservative</option>
                  <option value="moderate">Moderate</option>
                  <option value="aggressive">Aggressive</option>
                </select>
              </Field>
              <Field label="Monthly income" hint="Optional. Used for planning until records are enough.">
                <div className="amount-field"><span>₹</span><input type="number" min="0" step="1000" value={profile.monthly_income} onChange={(event) => setProfile({ ...profile, monthly_income: event.target.value })} /></div>
              </Field>
            </div>
            {profileError && <div className="form-error">{profileError}</div>}
            <div className="form-actions">
              <span className="form-muted">Member since {formatDate(user.created_at)}</span>
              <button type="submit" className="btn btn-primary" disabled={profileBusy}>{profileBusy ? <Spinner label="Saving…" /> : 'Save profile'}</button>
            </div>
          </form>
        </Card>

        <Card>
          <SectionTitle title="Security" description="Passwords are hashed; sessions use HTTP-only cookies and CSRF tokens." action={<LockKeyhole size={18} />} />
          <form className="stack-form" onSubmit={savePassword}>
            <Field label="Current password">
              <input type="password" required autoComplete="current-password" value={password.current_password} onChange={(event) => setPassword({ ...password, current_password: event.target.value })} />
            </Field>
            <Field label="New password" hint="At least 10 characters, including a letter and a number.">
              <input type="password" required minLength={10} autoComplete="new-password" value={password.new_password} onChange={(event) => setPassword({ ...password, new_password: event.target.value })} />
            </Field>
            <Field label="Confirm new password">
              <input type="password" required minLength={10} autoComplete="new-password" value={password.confirm} onChange={(event) => setPassword({ ...password, confirm: event.target.value })} />
            </Field>
            {passwordError && <div className="form-error">{passwordError}</div>}
            <div className="form-actions">
              <span className="form-muted"><KeyRound size={13} /> Changing a password does not delete data.</span>
              <button type="submit" className="btn btn-secondary" disabled={passwordBusy}>{passwordBusy ? <Spinner label="Updating…" /> : 'Change password'}</button>
            </div>
          </form>
        </Card>

        <Card>
          <SectionTitle title="Privacy & model" description="What leaves this machine, and what does not." action={<ShieldCheck size={18} />} />
          <div className="settings-status">
            <div>
              <span>Advisor mode</span>
              <Badge tone={advisor?.available ? 'sand' : 'green'} dot>{advisor?.available ? 'External LLM configured' : 'Deterministic, fully offline'}</Badge>
            </div>
            <div>
              <span>API endpoint</span>
              <code>{base}</code>
            </div>
            <div>
              <span>Encryption</span>
              <strong>Description and notes encrypted at rest</strong>
            </div>
            <div>
              <span>Demo account</span>
              <strong>{user.email === 'demo@clearpath.app' ? 'Yes — deletion disabled' : 'No'}</strong>
            </div>
          </div>
          <Callout tone={advisor?.available ? 'amber' : 'green'} title={advisor?.available ? 'A model provider is configured' : 'No external model is configured'} icon={Sparkles}>
            <p>
              {advisor?.available
                ? 'Questions are planned by the configured model. Tool results are redacted where appropriate, and every numeric claim is checked before display.'
                : 'All planning, computation and explanation runs locally. The only network request is to your own backend.'}
            </p>
          </Callout>
        </Card>

        <Card>
          <SectionTitle title="Your data" description="Export everything as JSON, or remove the account permanently." action={<Database size={18} />} />
          <div className="data-actions">
            <div>
              <strong>Export account data</strong>
              <p>Transactions, budgets, goals, contributions, debts, assets, conversations, literacy progress and activity history.</p>
              <button type="button" className="btn btn-secondary" onClick={exportData} disabled={exporting}>{exporting ? <Spinner /> : <Download size={15} />} Download JSON</button>
            </div>
            <div className="danger-zone">
              <strong>Delete account</strong>
              <p>This removes every record and cannot be undone. The demo account cannot be deleted.</p>
              {!deleteOpen ? (
                <button type="button" className="btn btn-danger" onClick={() => setDeleteOpen(true)}><Trash2 size={15} /> Delete account</button>
              ) : (
                <form className="delete-form" onSubmit={deleteAccount}>
                  <Field label="Confirm with your password">
                    <input type="password" required autoComplete="current-password" value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} />
                  </Field>
                  {deleteError && <div className="form-error">{deleteError}</div>}
                  <div className="row-actions">
                    <button type="button" className="btn btn-ghost" onClick={() => { setDeleteOpen(false); setDeletePassword(''); setDeleteError('') }}>Cancel</button>
                    <button type="submit" className="btn btn-danger" disabled={deleting}>{deleting ? <Spinner label="Deleting…" /> : 'Delete permanently'}</button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </Card>
      </div>

      <div className="settings-foot">
        <Landmark size={15} />
        <p>
          Clearpath is an educational planning tool, not a SEBI-registered investment adviser, lender or insurer.
          It does not connect to bank accounts and does not execute transactions.
        </p>
        <span className="security-stamp"><CheckCircle2 size={14} /> Local-first architecture</span>
      </div>
    </>
  )
}

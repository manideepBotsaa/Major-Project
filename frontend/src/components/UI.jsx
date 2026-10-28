import { useEffect } from 'react'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Inbox, Loader2, X } from 'lucide-react'
import { formatMoney, formatPct, titleCase } from '../lib/format'

export function Card({ children, className = '', as: Tag = 'section' }) {
  return <Tag className={`card ${className}`}>{children}</Tag>
}

export function PageHeader({ eyebrow, title, description, actions, children }) {
  return (
    <header className="page-header">
      <div className="page-heading">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
        {children}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function SectionTitle({ title, description, action }) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function StatCard({ label, value, note, icon: Icon, tone = 'green', trend, trendLabel }) {
  const positive = Number(trend) >= 0
  return (
    <Card className={`stat-card tone-${tone}`}>
      <div className="stat-top">
        <span>{label}</span>
        {Icon && (
          <i className="stat-icon">
            <Icon size={18} />
          </i>
        )}
      </div>
      <strong className="stat-value">{value}</strong>
      <div className="stat-foot">
        {trend !== undefined && trend !== null && (
          <span className={`trend ${positive ? 'up' : 'down'}`}>
            {positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {formatPct(Math.abs(Number(trend)), 1)}
          </span>
        )}
        <small>{trendLabel || note}</small>
      </div>
    </Card>
  )
}

export function ProgressBar({ value, max = 100, tone = 'green', height = 8, className = '' }) {
  const pct = Math.max(0, Math.min(100, max ? (Number(value) / Number(max)) * 100 : 0))
  return (
    <div
      className={`progress ${className}`}
      style={{ '--progress': `${pct}%`, '--progress-height': `${height}px` }}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <span className={`progress-fill progress-${tone}`} />
    </div>
  )
}

export function Badge({ children, tone = 'neutral', dot = false, className = '' }) {
  return (
    <span className={`badge badge-${tone} ${className}`}>
      {dot && <i className="badge-dot" />}
      {children}
    </span>
  )
}

export function statusTone(status) {
  return (
    {
      on_track: 'green',
      comfortable: 'green',
      affordable: 'green',
      achieved: 'green',
      strong: 'green',
      active: 'green',
      watch: 'amber',
      at_risk: 'amber',
      stretch: 'amber',
      building: 'amber',
      attention: 'amber',
      over: 'red',
      off_track: 'red',
      overdue: 'red',
      not_now: 'red',
      critical: 'red',
      low: 'red',
      paused: 'neutral',
      no_deadline: 'neutral',
    }[status] || 'neutral'
  )
}

export function Verdict({ verdict, children }) {
  return <Badge tone={statusTone(verdict)} dot>{children || titleCase(verdict)}</Badge>
}

export function EmptyState({ icon: Icon = Inbox, title = 'Nothing here yet', children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={24} />
      </span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <Card className="error-state">
      <AlertTriangle size={22} />
      <div>
        <strong>Something did not load</strong>
        <p>{message || 'Please try again.'}</p>
      </div>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </Card>
  )
}

export function Spinner({ label }) {
  return (
    <span className="spinner-wrap">
      <Loader2 size={16} className="spin" />
      {label && <span>{label}</span>}
    </span>
  )
}

export function LoadingScreen({ label = 'Loading your workspace…' }) {
  return (
    <div className="loading-screen">
      <div className="mark mark-pulse">c</div>
      <Spinner label={label} />
    </div>
  )
}

export function Skeleton({ className = '', lines = 1 }) {
  if (lines > 1) {
    return (
      <div className="skeleton-stack">
        {Array.from({ length: lines }).map((_, index) => (
          <div key={index} className={`skeleton ${className}`} style={{ width: `${92 - index * 7}%` }} />
        ))}
      </div>
    )
  }
  return <div className={`skeleton ${className}`} />
}

export function Modal({ open, onClose, title, eyebrow, children, footer, size = 'md' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <div>
            {eyebrow && <span className="eyebrow">{eyebrow}</span>}
            <h2>{title}</h2>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={19} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({ label, hint, error, children, className = '', htmlFor }) {
  return (
    <label className={`field ${className}`} htmlFor={htmlFor}>
      <span>{label}</span>
      {children}
      {error ? <small className="field-error">{error}</small> : hint ? <small>{hint}</small> : null}
    </label>
  )
}

export function Tabs({ tabs, active, onChange, className = '' }) {
  return (
    <div className={`tabs ${className}`} role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          className={active === tab.id ? 'active' : ''}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && <i>{tab.count}</i>}
        </button>
      ))}
    </div>
  )
}

export function KeyValue({ items, className = '' }) {
  return (
    <dl className={`key-values ${className}`}>
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Callout({ tone = 'green', title, children, icon: Icon }) {
  return (
    <div className={`callout callout-${tone}`}>
      {Icon && <Icon size={19} />}
      <div>
        {title && <strong>{title}</strong>}
        {children}
      </div>
    </div>
  )
}

export function Money({ value, currency = 'INR', toneAmount = false, className = '', options }) {
  return (
    <span className={`${toneAmount ? 'money' : ''} ${className}`}>
      {formatMoney(value, currency, options)}
    </span>
  )
}

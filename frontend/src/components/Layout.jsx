import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ArrowUpRight,
  BookOpen,
  Calculator,
  ChevronRight,
  CircleDollarSign,
  Compass,
  CreditCard,
  FlaskConical,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  ReceiptText,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  WalletCards,
  X,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { initials } from '../lib/format'

const NAV = [
  {
    label: 'Workspace',
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/transactions', label: 'Transactions', icon: ReceiptText },
      { to: '/budgets', label: 'Budgets', icon: WalletCards },
    ],
  },
  {
    label: 'Plan',
    items: [
      { to: '/goals', label: 'Goals', icon: Target },
      { to: '/debt', label: 'Debt', icon: CreditCard },
      { to: '/assets', label: 'Net worth', icon: CircleDollarSign },
    ],
  },
  {
    label: 'Understand',
    items: [
      { to: '/insights', label: 'Insights', icon: Gauge },
      { to: '/advisor', label: 'Advisor', icon: MessageSquareText },
      { to: '/momentum', label: 'Momentum', icon: Sparkles },
      { to: '/learn', label: 'Learn', icon: GraduationCap },
      { to: '/tools', label: 'Calculators', icon: Calculator },
    ],
  },
  {
    label: 'Project',
    items: [
      { to: '/research', label: 'Research', icon: FlaskConical },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

const TITLES = {
  '/': 'Overview',
  '/transactions': 'Transactions',
  '/budgets': 'Budgets',
  '/goals': 'Goals',
  '/debt': 'Debt',
  '/assets': 'Net worth',
  '/insights': 'Insights',
  '/advisor': 'Advisor',
  '/momentum': 'Momentum',
  '/learn': 'Financial literacy',
  '/tools': 'Calculators',
  '/research': 'Research',
  '/settings': 'Settings',
}

function SidebarContent({ onNavigate }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  return (
    <>
      <NavLink to="/" className="brand" onClick={onNavigate}>
        <span className="brand-mark">c</span>
        <span>clearpath</span>
      </NavLink>
      <div className="sidebar-nav">
        {NAV.map((group) => (
          <div className="nav-group" key={group.label}>
            <span className="nav-label">{group.label}</span>
            {group.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `nav-item ${isActive || (to !== '/' && location.pathname.startsWith(`${to}/`)) ? 'selected' : ''}`
                }
              >
                <Icon size={17} strokeWidth={1.9} />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <div className="sidebar-bottom">
        <div className="trust-box">
          <span className="trust-icon">
            <ShieldCheck size={17} />
          </span>
          <strong>Numbers first.</strong>
          <p>Every figure is computed by the financial engine, then checked before an answer is shown.</p>
          <NavLink to="/research" onClick={onNavigate}>
            How it works <ChevronRight size={13} />
          </NavLink>
        </div>
        <NavLink to="/settings" className="profile-row" onClick={onNavigate}>
          <span className="avatar">{initials(user?.name) || 'C'}</span>
          <span className="profile-copy">
            <strong>{user?.name}</strong>
            <small>{user?.email}</small>
          </span>
        </NavLink>
        <button type="button" className="signout-row" onClick={logout}>
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </>
  )
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [llm, setLlm] = useState(null)
  const location = useLocation()

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    api
      .advisorStatus()
      .then((data) => setLlm(data.llm))
      .catch(() => {})
  }, [])

  const title =
    TITLES[location.pathname] ||
    (location.pathname.startsWith('/learn/') ? 'Learn' : 'Clearpath')

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <SidebarContent />
      </aside>
      {mobileOpen && (
        <div className="mobile-drawer">
          <button type="button" className="drawer-backdrop" onClick={() => setMobileOpen(false)} aria-label="Close menu" />
          <aside className="drawer-panel">
            <button type="button" className="icon-btn drawer-close" onClick={() => setMobileOpen(false)} aria-label="Close menu">
              <X size={19} />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button type="button" className="icon-btn menu-btn" onClick={() => setMobileOpen(true)} aria-label="Open menu">
              <Menu size={20} />
            </button>
            <div className="breadcrumbs">
              <span>Workspace</span>
              <ChevronRight size={13} />
              <strong>{title}</strong>
            </div>
          </div>
          <div className="topbar-right">
            {llm && (
              <span className={`mode-pill ${llm.available ? 'mode-llm' : 'mode-rules'}`}>
                <i />
                {llm.available ? `${llm.provider} · grounded` : 'Deterministic advisor'}
              </span>
            )}
            <span className="topbar-date">
              {new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
            <NavLink to="/advisor" className="btn btn-primary btn-sm topbar-cta">
              <Compass size={15} /> Ask Clearpath
            </NavLink>
            <NavLink to="/settings" className="top-avatar" aria-label="Account settings">
              {initials(useAuthName()) || 'C'}
            </NavLink>
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>Clearpath · GroundedPath research system</span>
          <span>
            Educational planning, not investment advice. <ArrowUpRight size={12} />
          </span>
        </footer>
      </div>
    </div>
  )
}

function useAuthName() {
  const { user } = useAuth()
  return user?.name
}

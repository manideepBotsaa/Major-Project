import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { LoadingScreen } from './components/UI'
import { useAuth } from './context/AuthContext'
import Advisor from './pages/Advisor'
import Assets from './pages/Assets'
import Budgets from './pages/Budgets'
import Dashboard from './pages/Dashboard'
import Debts from './pages/Debts'
import Goals from './pages/Goals'
import Insights from './pages/Insights'
import Learn from './pages/Learn'
import Login from './pages/Login'
import Momentum from './pages/Momentum'
import NotFound from './pages/NotFound'
import Research from './pages/Research'
import Settings from './pages/Settings'
import Tools from './pages/Tools'
import Transactions from './pages/Transactions'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

function ProtectedLayout() {
  const { user, loading } = useAuth()
  if (loading) return <LoadingScreen label="Opening your workspace…" />
  if (!user) return <Navigate to="/login" replace />
  return <Layout />
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/budgets" element={<Budgets />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/debt" element={<Debts />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/advisor" element={<Advisor />} />
          <Route path="/momentum" element={<Momentum />} />
          <Route path="/learn" element={<Learn />} />
          <Route path="/learn/:slug" element={<Learn />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/research" element={<Research />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </>
  )
}

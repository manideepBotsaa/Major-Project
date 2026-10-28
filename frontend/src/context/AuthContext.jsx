import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    api
      .me()
      .then((data) => {
        if (active) setUser(data.user)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false)
      })
    const onUnauthorized = () => setUser(null)
    window.addEventListener('clearpath:unauthorized', onUnauthorized)
    return () => {
      active = false
      window.removeEventListener('clearpath:unauthorized', onUnauthorized)
    }
  }, [])

  const login = useCallback(async (credentials) => {
    const data = await api.login(credentials)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (values) => {
    const data = await api.register(values)
    setUser(data.user)
    return data.user
  }, [])

  const demoLogin = useCallback(async () => {
    const data = await api.demoLogin()
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const updateUser = useCallback((nextUser) => {
    setUser((current) => (nextUser ? { ...current, ...nextUser } : nextUser))
  }, [])

  const refreshUser = useCallback(async () => {
    const data = await api.me()
    setUser(data.user)
    return data.user
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, register, demoLogin, logout, updateUser, refreshUser }),
    [user, loading, login, register, demoLogin, logout, updateUser, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

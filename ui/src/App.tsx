import { useState, useEffect } from 'react'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { API } from './config'

interface User {
  username: string
  display_name: string
}

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem('snoopi_token')
    if (saved) {
      fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${saved}` } })
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(u => { setToken(saved); setUser(u) })
        .catch(() => localStorage.removeItem('snoopi_token'))
    }
  }, [])

  const handleLogin = (t: string, u: User) => {
    setToken(t)
    setUser(u)
  }

  const handleLogout = () => {
    localStorage.removeItem('snoopi_token')
    setToken(null)
    setUser(null)
  }

  if (!token || !user) {
    return <LoginPage onLogin={handleLogin} />
  }

  return <DashboardPage user={user} token={token} onLogout={handleLogout} />
}

export default App

import { useState } from 'react'
import Login from './pages/Login/Login'
import Dashboard from './pages/Dashboard/Dashboard'
import SuperAdminConsole from './pages/SuperAdmin/SuperAdminConsole'
import type { Session } from './lib/api'

const SESSION_STORAGE_KEY = 'pestwatcher.session'

function loadStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

function App() {
  const [session, setSession] = useState<Session | null>(loadStoredSession)

  const handleLoginSuccess = (next: Session) => {
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(next))
    } catch {
      // localStorage unavailable (private mode, quota) — session still works for this tab
    }
    setSession(next)
  }

  const handleLogout = () => {
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY)
    } catch {
      // ignore
    }
    setSession(null)
  }

  if (!session) {
    return <Login onLoginSuccess={handleLoginSuccess} />
  }

  if (session.user.accountType === 'superadmin') {
    return (
      <SuperAdminConsole
        user={session.user}
        accessToken={session.accessToken}
        onLogout={handleLogout}
        onSessionExpired={handleLogout}
      />
    )
  }

  return <Dashboard user={session.user} onLogout={handleLogout} />
}

export default App

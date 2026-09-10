import { useState } from 'react'
import Login from './pages/Login/Login'
import Dashboard from './pages/Dashboard/Dashboard'
import type { LguUser } from './lib/api'

function App() {
  const [user, setUser] = useState<LguUser | null>(null)

  if (!user) {
    return <Login onLoginSuccess={setUser} />
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} />
}

export default App

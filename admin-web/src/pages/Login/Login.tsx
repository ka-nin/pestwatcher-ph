import { useState } from 'react'
import bgImg from '../../assets/bg-img.png'
import logo from '../../assets/logo.png'
import { login, type LguUser } from '../../lib/api'
import './Login.css'

interface LoginProps {
  onLoginSuccess: (user: LguUser) => void
}

function Login({ onLoginSuccess }: LoginProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await login(username, password)
      onLoginSuccess(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to log in right now')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-image" style={{ backgroundImage: `url(${bgImg})` }}>
        <div className="login-image-overlay">
          <span className="login-image-brand">PESTWATCHER PH</span>
          <span className="login-image-tagline">Agricultural pest monitoring</span>
        </div>
      </div>

      <div className="login-panel">
        <div className="login-brand">
          <img src={logo} alt="PestWatcher PH Logo" className="login-logo" />
          <h1>PestWatcher PH</h1>
          <p className="login-subtitle">Agricultural pest monitoring</p>
        </div>

        <div className="login-card">
          <h2>Log in</h2>
          <p className="login-card-subtitle">Access your monitoring dashboard</p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && <p className="login-error">{error}</p>}

            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? 'Logging in…' : 'Log In'}
            </button>
          </form>

          <a href="#" className="login-forgot">
            Forgot Password?
          </a>
        </div>

        <p className="login-footer">© 2026 PestWatcher PH. All rights reserved.</p>
      </div>
    </div>
  )
}

export default Login

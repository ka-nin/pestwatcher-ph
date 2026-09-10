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
  const [showPassword, setShowPassword] = useState(false)

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
              <div className="password-input">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 3l18 18" strokeLinecap="round" />
                      <path
                        d="M10.6 10.6a2 2 0 0 0 2.8 2.8M6.6 6.7C4.5 8.1 3 10 2 12c1.6 3.6 5 7 10 7 1.7 0 3.2-.4 4.6-1.1M9.9 4.2A10.4 10.4 0 0 1 12 4c5 0 8.4 3.4 10 7-.5 1.2-1.2 2.4-2.1 3.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path
                        d="M2 12c1.6-3.6 5-7 10-7s8.4 3.4 10 7c-1.6 3.6-5 7-10 7s-8.4-3.4-10-7Z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
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

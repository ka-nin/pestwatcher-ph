import { useState } from 'react'
import bgImg from '../assets/bg-img.png'
import logo from '../assets/logo.png'
import './Login.css'

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: wire up authentication
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

            <button type="submit" className="login-submit">
              Log In
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

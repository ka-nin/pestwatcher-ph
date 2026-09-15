import { useState } from 'react'
import logo from '../../assets/logo.png'
import type { SuperAdminUser } from '../../lib/api'
import OverviewPage from './OverviewPage'
import LguAccountsPage from './LguAccountsPage'
import SettingsPage from './SettingsPage'
import '../Dashboard/Dashboard.css'
import './SuperAdminConsole.css'

interface SuperAdminConsoleProps {
  user: SuperAdminUser
  accessToken: string
  onLogout: () => void
  onSessionExpired: () => void
}

type PageKey = 'overview' | 'accounts' | 'settings'

const navItems: { key: PageKey; label: string }[] = [
  { key: 'overview', label: 'Municipalities Overview' },
  { key: 'accounts', label: 'LGU Accounts' },
  { key: 'settings', label: 'System Settings' },
]

const navIcons: Record<PageKey, React.ReactNode> = {
  overview: <path d="M3 12h4l2 6 4-14 2 8h6" strokeLinecap="round" strokeLinejoin="round" />,
  accounts: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M2 20c0-3.3 3.1-6 7-6s7 2.7 7 6" strokeLinecap="round" />
      <path d="M16 4.5a3 3 0 0 1 0 5.8M20 20c0-2.8-2.2-5.1-5-5.8" strokeLinecap="round" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path
        d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  ),
}

function SuperAdminConsole({ user, accessToken, onLogout, onSessionExpired }: SuperAdminConsoleProps) {
  const [activePage, setActivePage] = useState<PageKey>('overview')
  const activeLabel = navItems.find((item) => item.key === activePage)?.label ?? 'Overview'

  return (
    <div className="dashboard superadmin-console">
      <div className="dashboard-body">
        <aside className="dashboard-sidebar">
          <div className="sidebar-brand">
            <img src={logo} alt="PestWatcher PH Logo" className="sidebar-logo" />
            <div>
              <div className="sidebar-brand-name">PestWatcher PH</div>
              <div className="sidebar-brand-tagline">SuperAdmin Console</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <a
                key={item.key}
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  setActivePage(item.key)
                }}
                className={`sidebar-nav-item${activePage === item.key ? ' active' : ''}`}
              >
                <svg
                  className="sidebar-nav-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  {navIcons[item.key]}
                </svg>
                {item.label}
              </a>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-province">
              <span className="sidebar-province-label">ROLE</span>
              <div className="sidebar-province-value">SuperAdmin</div>
            </div>
            <button type="button" onClick={onLogout} className="sidebar-logout">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Logout
            </button>
          </div>
        </aside>

        <main className="dashboard-main">
          <header className="dashboard-header">
            <h1>{activeLabel}</h1>
            <div className="dashboard-user">
              <span className="dashboard-user-label">SuperAdmin</span>
              <span className="dashboard-user-name">{user.fullName}</span>
            </div>
          </header>

          {activePage === 'overview' && (
            <OverviewPage accessToken={accessToken} onSessionExpired={onSessionExpired} />
          )}
          {activePage === 'accounts' && (
            <LguAccountsPage accessToken={accessToken} onSessionExpired={onSessionExpired} />
          )}
          {activePage === 'settings' && (
            <SettingsPage accessToken={accessToken} onSessionExpired={onSessionExpired} />
          )}
        </main>
      </div>
    </div>
  )
}

export default SuperAdminConsole

import { useEffect, useState } from 'react'
import {
  createLguUser,
  deleteLguUser,
  fetchLguUsers,
  updateLguUser,
  type LguAccountAdmin,
} from '../../lib/api'

interface LguAccountsPageProps {
  accessToken: string
  onSessionExpired: () => void
}

interface FormState {
  username: string
  password: string
  roleLevel: string
  province: string
  municipality: string
  latitude: string
  longitude: string
}

const emptyForm: FormState = {
  username: '',
  password: '',
  roleLevel: 'LGU_Tech',
  province: '',
  municipality: '',
  latitude: '',
  longitude: '',
}

function LguAccountsPage({ accessToken, onSessionExpired }: LguAccountsPageProps) {
  const [accounts, setAccounts] = useState<LguAccountAdmin[] | null>(null)
  const [error, setError] = useState('')
  const [editingUsername, setEditingUsername] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const loadAccounts = () => {
    fetchLguUsers(accessToken)
      .then(setAccounts)
      .catch((err: Error) => {
        if (err.message.startsWith('Session expired')) {
          onSessionExpired()
        } else {
          setError(err.message)
        }
      })
  }

  useEffect(loadAccounts, [accessToken]) // eslint-disable-line react-hooks/exhaustive-deps

  const startEdit = (account: LguAccountAdmin) => {
    setShowCreateForm(false)
    setEditingUsername(account.username)
    setForm({
      username: account.username,
      password: '',
      roleLevel: account.roleLevel,
      province: account.province,
      municipality: account.municipality,
      latitude: String(account.latitude),
      longitude: String(account.longitude),
    })
    setFormError('')
  }

  const startCreate = () => {
    setEditingUsername(null)
    setShowCreateForm(true)
    setForm(emptyForm)
    setFormError('')
  }

  const cancelForm = () => {
    setEditingUsername(null)
    setShowCreateForm(false)
    setFormError('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')

    const latitude = Number(form.latitude)
    const longitude = Number(form.longitude)
    if (!form.province || !form.municipality || Number.isNaN(latitude) || Number.isNaN(longitude)) {
      setFormError('Province, municipality, and numeric coordinates are required')
      return
    }

    setSaving(true)
    try {
      if (editingUsername) {
        await updateLguUser(accessToken, editingUsername, {
          password: form.password || undefined,
          roleLevel: form.roleLevel,
          province: form.province,
          municipality: form.municipality,
          latitude,
          longitude,
        })
      } else {
        if (!form.username || !form.password) {
          setFormError('Username and password are required')
          setSaving(false)
          return
        }
        await createLguUser(accessToken, {
          username: form.username,
          password: form.password,
          roleLevel: form.roleLevel,
          province: form.province,
          municipality: form.municipality,
          latitude,
          longitude,
        })
      }
      cancelForm()
      loadAccounts()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save account')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (username: string) => {
    if (!window.confirm(`Permanently delete LGU account "${username}"? This cannot be undone.`)) return
    try {
      await deleteLguUser(accessToken, username)
      loadAccounts()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete account')
    }
  }

  const handleToggleActive = async (account: LguAccountAdmin) => {
    try {
      await updateLguUser(accessToken, account.username, { isActive: !account.isActive })
      loadAccounts()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update account status')
    }
  }

  const formOpen = showCreateForm || editingUsername !== null

  return (
    <section className="panel admin-panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">LGU Accounts</div>
          <div className="panel-subtitle">Municipal technician accounts — in-memory, resets on server restart</div>
        </div>
        {!formOpen && (
          <button type="button" className="admin-btn admin-btn-primary" onClick={startCreate}>
            + New Account
          </button>
        )}
      </div>

      {formOpen && (
        <form className="admin-form" onSubmit={handleSubmit}>
          <div className="admin-form-title">{editingUsername ? `Edit ${editingUsername}` : 'New LGU Account'}</div>
          <div className="admin-form-grid">
            {!editingUsername && (
              <label className="admin-form-field">
                Username
                <input
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  required
                />
              </label>
            )}
            <label className="admin-form-field">
              {editingUsername ? 'New Password (leave blank to keep)' : 'Password'}
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required={!editingUsername}
              />
            </label>
            <label className="admin-form-field">
              Role Level
              <input
                value={form.roleLevel}
                onChange={(e) => setForm({ ...form, roleLevel: e.target.value })}
              />
            </label>
            <label className="admin-form-field">
              Province
              <input
                value={form.province}
                onChange={(e) => setForm({ ...form, province: e.target.value })}
                required
              />
            </label>
            <label className="admin-form-field">
              Municipality
              <input
                value={form.municipality}
                onChange={(e) => setForm({ ...form, municipality: e.target.value })}
                required
              />
            </label>
            <label className="admin-form-field">
              Latitude
              <input
                value={form.latitude}
                onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                required
              />
            </label>
            <label className="admin-form-field">
              Longitude
              <input
                value={form.longitude}
                onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                required
              />
            </label>
          </div>

          {formError && <p className="stat-card-error">{formError}</p>}

          <div className="admin-form-actions">
            <button type="submit" className="admin-btn admin-btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="admin-btn" onClick={cancelForm}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {error ? (
        <p className="stat-card-error">{error}</p>
      ) : accounts === null ? (
        <p className="stat-card-loading">Loading accounts…</p>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Province</th>
                <th>Municipality</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.username}>
                  <td>{account.username}</td>
                  <td>{account.roleLevel}</td>
                  <td>{account.province}</td>
                  <td>{account.municipality}</td>
                  <td>
                    <span className={account.isActive ? 'admin-status-active' : 'admin-status-inactive'}>
                      {account.isActive ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="admin-table-actions">
                    <button type="button" className="admin-link-btn" onClick={() => startEdit(account)}>
                      Edit
                    </button>
                    <button type="button" className="admin-link-btn" onClick={() => handleToggleActive(account)}>
                      {account.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      className="admin-link-btn admin-link-btn-danger"
                      onClick={() => handleDelete(account.username)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default LguAccountsPage

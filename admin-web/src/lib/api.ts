export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5000'

export interface LguUser {
  username: string
  roleLevel: string
  province: string
  municipality: string
}

interface LoginSuccess {
  user: LguUser
}

interface LoginFailure {
  message: string
}

export async function login(username: string, password: string): Promise<LguUser> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const data: LoginSuccess | LoginFailure = await res.json()

  if (!res.ok) {
    throw new Error((data as LoginFailure).message ?? 'Login failed')
  }

  return (data as LoginSuccess).user
}

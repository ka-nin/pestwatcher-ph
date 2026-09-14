import { createContext, useContext, useEffect, useState } from 'react';

const STORAGE_KEY = 'pestwatcher.user';
const GROWTH_STAGE_KEY = 'pestwatcher.growthStage';

const AuthContext = createContext(null);

function readStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function readStoredGrowthStage() {
  try {
    return localStorage.getItem(GROWTH_STAGE_KEY) || 'Tillering';
  } catch {
    return 'Tillering';
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);
  const [growthStage, setGrowthStage] = useState(readStoredGrowthStage);

  useEffect(() => {
    try {
      if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // localStorage unavailable (private browsing, etc.) — session just won't persist.
    }
  }, [user]);

  useEffect(() => {
    try {
      localStorage.setItem(GROWTH_STAGE_KEY, growthStage);
    } catch {
      // ignore
    }
  }, [growthStage]);

  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{ user, setUser, logout, growthStage, setGrowthStage }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

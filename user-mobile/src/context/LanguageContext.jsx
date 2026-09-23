import { createContext, useContext, useEffect, useState } from 'react';
import { translations } from '../i18n/strings';

const STORAGE_KEY = 'pestwatcher.language';
const LanguageContext = createContext(null);

function readStoredLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === 'en' ? 'en' : 'fil';
  } catch {
    return 'fil';
  }
}

export function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(readStoredLanguage);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // localStorage unavailable (private browsing, etc.) — choice just won't persist.
    }
  }, [language]);

  // Falls back to Filipino, then to the raw key, so a missing translation
  // renders something visible instead of blank text.
  const t = (key) => translations[language]?.[key] ?? translations.fil[key] ?? key;

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider');
  return ctx;
}

import { useLanguage } from '../context/LanguageContext';
import './LanguageToggle.css';

// Compact segmented EN/FIL switch — persisted via LanguageContext
// (localStorage), applied wherever a screen reads strings through t().
export default function LanguageToggle({ variant = 'dark' }) {
  const { language, setLanguage } = useLanguage();

  return (
    <div className={`language-toggle language-toggle-${variant}`} role="group" aria-label="Language">
      <button
        type="button"
        className={`language-toggle-option${language === 'fil' ? ' active' : ''}`}
        onClick={() => setLanguage('fil')}
      >
        FIL
      </button>
      <button
        type="button"
        className={`language-toggle-option${language === 'en' ? ' active' : ''}`}
        onClick={() => setLanguage('en')}
      >
        EN
      </button>
    </div>
  );
}

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import riceFieldImg from '../assets/rice-field.png';
import logoImg from '../assets/logo.png';
import { login } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './Welcome.css';

export default function Welcome() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState('farmer_demo');
  const [password, setPassword] = useState('RicePest!Demo2026');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(username, password);
      setUser(user);
      navigate('/home');
    } catch (err) {
      setError(err.message || 'Hindi ma-login. Pakisuri ang username at password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="welcome-screen" style={{ backgroundImage: `url(${riceFieldImg})` }}>
      <div className="welcome-content">
        <div className="welcome-brand-block">
          <img src={logoImg} alt="PestWatcher PH" className="welcome-logo-img" />
          <h1>
            PESTWATCHER<sup>PH</sup>
          </h1>
          <p>Pangmatagalang solusyon sa pagsasaka para sa mas magandang bukas</p>
        </div>

        {showForm ? (
          <form className="welcome-login-form" onSubmit={handleLogin}>
            {error && <p className="welcome-login-error">{error}</p>}
            <input
              className="welcome-login-input"
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
            <input
              className="welcome-login-input"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <button className="welcome-cta" type="submit" disabled={loading}>
              {loading ? 'Naglo-log in...' : 'Mag-login'}
            </button>
          </form>
        ) : (
          <button className="welcome-cta" onClick={() => setShowForm(true)}>
            Simulan
          </button>
        )}
      </div>
    </div>
  );
}

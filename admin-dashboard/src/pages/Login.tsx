import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiCall } from '../services/api';
import { LogIn, ShieldCheck, Sparkles, Cpu, AlertCircle, RefreshCw } from 'lucide-react';

export default function Login() {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [password, setPassword] = useState('password123'); // Default for hackathon
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', phoneNumber);
      formData.append('password', password);

      const data = await apiCall('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
      });
      
      localStorage.setItem('jwt_token', data.access_token);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div className="glass" style={{ padding: '40px', width: '100%', maxWidth: '440px', position: 'relative', overflow: 'hidden' }}>
        
        {/* Decorative inner glow header */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '32px' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            padding: '16px',
            borderRadius: '24px',
            marginBottom: '16px',
            boxShadow: '0 8px 32px rgba(16, 185, 129, 0.25)'
          }}>
            <Cpu size={40} color="#34d399" />
          </div>
          
          <div className="glass-pill" style={{ marginBottom: '12px', background: 'rgba(16, 185, 129, 0.15)', borderColor: 'rgba(52, 211, 153, 0.4)' }}>
            <Sparkles size={14} color="#34d399" />
            <span style={{ color: '#34d399' }}>AI BIOMASS VALUATION ENGINE</span>
          </div>

          <h2 style={{ fontSize: '2.2rem', fontWeight: '800', textAlign: 'center', color: '#fff', letterSpacing: '-0.5px' }}>
            AB<span style={{ color: '#34d399' }}>VE</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', marginTop: '4px' }}>
            Agri-Biomass Valuation & Fleet Logistics Engine
          </p>
        </div>
        
        {error && (
          <div style={{ 
            background: 'rgba(239, 68, 68, 0.15)', 
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#f87171', 
            padding: '14px', 
            borderRadius: '12px', 
            marginBottom: '20px',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backdropFilter: 'blur(10px)'
          }}>
            <AlertCircle size={18} color="#f87171" /> {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div className="input-group">
            <label style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Phone Number / Username</span>
              <span style={{ fontSize: '0.75rem', color: '#34d399' }}>Required</span>
            </label>
            <input 
              type="text" 
              value={phoneNumber} 
              onChange={(e) => setPhoneNumber(e.target.value)} 
              placeholder="Enter phone or admin id (e.g. 12345)"
              required 
            />
          </div>
          <div className="input-group">
            <label style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Security Password</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Default: password123</span>
            </label>
            <input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              placeholder="••••••••••••"
              required 
            />
          </div>
          
          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '12px', padding: '14px', fontSize: '1rem', borderRadius: '14px' }} disabled={loading}>
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <RefreshCw size={18} className="spin" /> Authenticating Engine...
              </span>
            ) : (
              <>
                <LogIn size={20} /> Access Control Center
              </>
            )}
          </button>
        </form>

        <div style={{ marginTop: '28px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
          <ShieldCheck size={16} color="#34d399" />
          <span>256-bit Encrypted • YOLOv8 + OR-Tools Active</span>
        </div>
      </div>
    </div>
  );
}

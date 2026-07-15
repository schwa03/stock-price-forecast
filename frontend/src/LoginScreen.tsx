import { useState } from 'react';
import axios from 'axios';
import { Lock } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export default function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/api/auth/login`, { password });
      onSuccess();
    } catch {
      setError('パスワードが違います');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)', padding: 'var(--s5)'
    }}>
      <form onSubmit={handleSubmit} className="card" style={{
        width: '100%', maxWidth: '360px', padding: 'var(--s6)', display: 'flex',
        flexDirection: 'column', gap: 'var(--s4)'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--s2)' }}>
          <Lock size={28} color="var(--pr)" />
          <div style={{ fontWeight: 800, fontSize: 'var(--lg)' }}>日本株 売買シグナル基盤</div>
          <div style={{ fontSize: 'var(--xs)', color: 'var(--tm)' }}>自分専用ページです。パスワードを入力してください。</div>
        </div>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="パスワード"
          autoFocus
          style={{
            width: '100%', padding: '.85rem .95rem', border: '1px solid var(--bd)',
            borderRadius: 'var(--r1)', background: 'var(--sf2)', color: 'var(--tx)',
            fontFamily: 'var(--font)'
          }}
        />

        {error && <div style={{ color: 'var(--er, #d64545)', fontSize: 'var(--sm)' }}>{error}</div>}

        <button type="submit" className="btn" disabled={loading || !password}>
          {loading ? 'ログイン中...' : 'ログイン'}
        </button>
      </form>
    </div>
  );
}

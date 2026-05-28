import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/client';
import { Leaf, Eye, EyeOff, AlertCircle, ShieldCheck, Database, BarChart3, ArrowRight, Activity } from 'lucide-react';

const FEATURES = [
  { icon: ShieldCheck, title: 'Audit-First Provenance', desc: 'Immutable raw payloads with SHA-256 hashes. Every transformation logged with before/after diffs.' },
  { icon: Database, title: 'Source-Agnostic Normalization', desc: 'SAP MM, Utility Interval, Travel — parsed to canonical records through separate failure domains.' },
  { icon: BarChart3, title: 'Deterministic Confidence', desc: 'Rule-based deduction scoring. No black-box ML. Every score drop is fully explainable.' },
  { icon: Activity, title: 'Analyst Review Workflow', desc: 'BLOCKING flags prevent approval. Append-only decision logs with full reviewer attribution.' },
];

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch {
      setError('Invalid credentials. Check the project README for demo accounts.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel — Hero */}
      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden"
           style={{ background: 'linear-gradient(135deg, #1B5E20 0%, #2E9844 35%, #0bafd0 100%)' }}>
        {/* Animated decorative elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-16 left-16 w-72 h-72 rounded-full bg-white/[0.04] blur-3xl"
               style={{ animation: 'float 8s ease-in-out infinite' }} />
          <div className="absolute bottom-24 right-12 w-96 h-96 rounded-full bg-white/[0.04] blur-3xl"
               style={{ animation: 'float 10s ease-in-out infinite 2s' }} />
          <div className="absolute top-1/2 left-1/3 w-48 h-48 rounded-full bg-white/[0.06] blur-2xl"
               style={{ animation: 'float 7s ease-in-out infinite 1s' }} />
          {/* Dot grid */}
          <div className="absolute inset-0 opacity-[0.04]"
               style={{ backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)', backgroundSize: '28px 28px' }} />
          {/* Floating leaves */}
          <Leaf className="absolute top-[12%] right-[18%] w-20 h-20 text-white/[0.07]"
                style={{ animation: 'float 9s ease-in-out infinite', transform: 'rotate(15deg)' }} />
          <Leaf className="absolute bottom-[20%] left-[12%] w-14 h-14 text-white/[0.06]"
                style={{ animation: 'float 11s ease-in-out infinite 3s', transform: 'rotate(-30deg)' }} />
          <Leaf className="absolute top-[55%] right-[8%] w-10 h-10 text-white/[0.08]"
                style={{ animation: 'float 8s ease-in-out infinite 1.5s', transform: 'rotate(80deg)' }} />
        </div>

        <div className={`relative z-10 flex flex-col justify-center px-16 py-12 max-w-[640px] transition-all duration-700 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {/* Logo */}
          <div className="flex items-center gap-3 mb-14">
            <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center border border-white/20 shadow-lg">
              <Leaf className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">Breathe ESG</h1>
              <p className="text-xs text-white/50 font-medium">Activity Ingestion & Review Platform</p>
            </div>
          </div>

          {/* Headline */}
          <h2 className="text-5xl font-extrabold text-white leading-[1.1] mb-5 tracking-tight">
            ESG data you<br />
            can actually<br />
            <span className="text-white/80">trust.</span>
          </h2>
          <p className="text-base text-white/60 mb-14 leading-relaxed max-w-md">
            Not another carbon dashboard. An audit-grade ingestion pipeline with layered normalization and analyst review workflows — built for data provenance, not data visualization.
          </p>

          {/* Feature cards */}
          <div className="space-y-3 stagger-children">
            {FEATURES.map((f, i) => (
              <div key={i} className="flex items-start gap-4 p-4 rounded-2xl bg-white/[0.06] backdrop-blur-sm border border-white/[0.08]
                         hover:bg-white/[0.1] hover:border-white/[0.15] transition-all duration-300 group cursor-default">
                <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center flex-shrink-0 group-hover:bg-white/15 group-hover:scale-105 transition-all duration-300">
                  <f.icon size={18} className="text-white/80" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white mb-0.5">{f.title}</h3>
                  <p className="text-xs text-white/50 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Bottom stat strip */}
          <div className="flex items-center gap-10 mt-14 pt-8 border-t border-white/10">
            {[
              { value: '3', label: 'Source Parsers' },
              { value: '19', label: 'Anomaly Types' },
              { value: '5', label: 'Audit Layers' },
            ].map((s) => (
              <div key={s.label}>
                <p className="text-3xl font-extrabold text-white tracking-tight">{s.value}</p>
                <p className="text-xs text-white/40 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel — Login Form */}
      <div className="flex-1 flex items-center justify-center px-8 bg-white">
        <div className={`w-full max-w-[380px] transition-all duration-700 delay-200 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          {/* Mobile logo */}
          <div className="lg:hidden text-center mb-10">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl shadow-lg mb-4"
                 style={{ background: 'linear-gradient(135deg, #2E9844 0%, #0bafd0 100%)' }}>
              <Leaf className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-txt-primary mb-1 tracking-tight">Breathe ESG</h1>
            <p className="text-sm text-txt-muted">Activity Ingestion & Review Platform</p>
          </div>

          {/* Form header */}
          <div className="mb-10">
            <h2 className="text-3xl font-extrabold text-txt-primary tracking-tight mb-2">Sign in</h2>
            <p className="text-sm text-txt-muted leading-relaxed">Access the analyst review workspace and ingestion pipeline</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="login-username" className="block text-xs font-semibold text-txt-secondary mb-2 tracking-wide">
                Username
              </label>
              <input id="login-username" type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                     className="input" placeholder="Enter your username" required autoFocus />
            </div>

            <div>
              <label htmlFor="login-password" className="block text-xs font-semibold text-txt-secondary mb-2 tracking-wide">
                Password
              </label>
              <div className="relative">
                <input id="login-password" type={showPassword ? 'text' : 'password'} value={password}
                       onChange={(e) => setPassword(e.target.value)} className="input pr-10" placeholder="Enter password" required />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-txt-faint hover:text-txt-secondary transition-colors duration-200">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-50 border border-red-200 animate-fade-in">
                <AlertCircle size={14} className="text-red-500 flex-shrink-0" />
                <span className="text-xs text-red-600 font-medium">{error}</span>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-base mt-2">
              {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : null}
              <span>{loading ? 'Signing in...' : 'Sign in'}</span>
              {!loading && <ArrowRight size={18} />}
            </button>
          </form>

          <p className="text-2xs text-txt-faint text-center mt-8 leading-relaxed">
            Breathe ESG Platform v1.0 — Built for the Breathe ESG Technical Assignment
          </p>
        </div>
      </div>
    </div>
  );
}

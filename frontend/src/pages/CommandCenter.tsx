import { useState, useEffect, useRef } from 'react';
import { fetchIngestionStats, fetchJobs, uploadFile, fetchReviewQueue } from '../api/client';
import type { IngestionStats, IngestionJob, QueueRecord } from '../types';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import {
  Upload, FileSpreadsheet, Zap, Plane, CheckCircle2, XCircle, Clock,
  ArrowUpRight, RefreshCw, TrendingUp, AlertTriangle, ShieldAlert, Activity,
} from 'lucide-react';

const SOURCE_CONFIG = {
  SAP_MM: { label: 'SAP MM', icon: FileSpreadsheet, gradient: 'linear-gradient(135deg, #EA580C 0%, #F59E0B 100%)', color: '#EA580C' },
  UTILITY_INTERVAL: { label: 'Utility', icon: Zap, gradient: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)', color: '#2563EB' },
  TRAVEL_CONCUR: { label: 'Travel', icon: Plane, gradient: 'linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)', color: '#7C3AED' },
} as const;

const SCOPE_COLORS = { SCOPE_1: '#EF4444', SCOPE_2: '#3B82F6', SCOPE_3: '#8B5CF6' };
const CONFIDENCE_COLORS = ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'];

function AnimatedCounter({ target, duration = 800 }: { target: number; duration?: number }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    let start = 0; const step = Math.max(1, Math.ceil(target / (duration / 16)));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else setCount(start);
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return <span>{count.toLocaleString('en-IN')}</span>;
}

export default function CommandCenter() {
  const [stats, setStats] = useState<IngestionStats[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [records, setRecords] = useState<QueueRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadSource, setUploadSource] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, j, q] = await Promise.all([fetchIngestionStats(), fetchJobs(), fetchReviewQueue({})]);
      setStats(s); setJobs(j.results || []); setRecords(q.results || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !uploadSource) return;
    setUploading(true); setUploadResult(null);
    try {
      const job = await uploadFile(file, uploadSource);
      setUploadResult({ ok: true, msg: `Ingested ${job.parsed_rows}/${job.total_rows} rows — ${job.suspicious_rows} suspicious` });
      loadData();
    } catch (err: any) {
      setUploadResult({ ok: false, msg: err.response?.data?.error || 'Upload failed' });
    } finally { setUploading(false); setUploadSource(null); if (fileRef.current) fileRef.current.value = ''; }
  };

  const triggerUpload = (source: string) => { setUploadSource(source); setTimeout(() => fileRef.current?.click(), 50); };

  // Computed analytics
  const totalRows = stats.reduce((s, x) => s + x.total_rows, 0);
  const totalPending = stats.reduce((s, x) => s + x.pending_review, 0);
  const totalFailed = stats.reduce((s, x) => s + x.failed_rows, 0);
  const totalJobs = stats.reduce((s, x) => s + x.total_jobs, 0);

  // Scope distribution
  const scopeCounts: Record<string, number> = {};
  records.forEach((r) => { if (r.scope_category) scopeCounts[r.scope_category] = (scopeCounts[r.scope_category] || 0) + 1; });
  const scopeData = Object.entries(scopeCounts).map(([name, value]) => ({ name: name.replace('_', ' '), value, fill: SCOPE_COLORS[name as keyof typeof SCOPE_COLORS] || '#9CA3AF' }));

  // Emissions by source
  const emissionsBySource: Record<string, number> = {};
  records.forEach((r) => {
    if (r.calculated_emissions) {
      const src = SOURCE_CONFIG[r.source_type as keyof typeof SOURCE_CONFIG]?.label || r.source_type;
      emissionsBySource[src] = (emissionsBySource[src] || 0) + parseFloat(r.calculated_emissions);
    }
  });
  const emissionsData = Object.entries(emissionsBySource).map(([name, value]) => ({
    name, value: Math.round(value),
    fill: name === 'SAP MM' ? '#EA580C' : name === 'Utility' ? '#2563EB' : '#7C3AED',
  }));

  // Confidence histogram
  const confBuckets = [0, 0, 0, 0]; // 0-35, 35-60, 60-85, 85-100
  records.forEach((r) => {
    const s = parseFloat(r.confidence_score) * 100;
    if (s < 35) confBuckets[0]++;
    else if (s < 60) confBuckets[1]++;
    else if (s < 85) confBuckets[2]++;
    else confBuckets[3]++;
  });
  const confidenceData = [
    { range: '0–35%', count: confBuckets[0], fill: '#EF4444' },
    { range: '35–60%', count: confBuckets[1], fill: '#F59E0B' },
    { range: '60–85%', count: confBuckets[2], fill: '#3B82F6' },
    { range: '85–100%', count: confBuckets[3], fill: '#10B981' },
  ];

  // Anomaly breakdown
  const flagCounts: Record<string, number> = {};
  records.forEach((r) => {
    if (r.blocking_count > 0) flagCounts['Blocking'] = (flagCounts['Blocking'] || 0) + r.blocking_count;
    if (r.warning_count > 0) flagCounts['Warning'] = (flagCounts['Warning'] || 0) + r.warning_count;
    const infoCount = r.anomaly_summary.length - r.blocking_count - r.warning_count;
    if (infoCount > 0) flagCounts['Info'] = (flagCounts['Info'] || 0) + infoCount;
  });
  const flagData = Object.entries(flagCounts).map(([name, value]) => ({
    name, value, fill: name === 'Blocking' ? '#EF4444' : name === 'Warning' ? '#F59E0B' : '#6366F1',
  }));

  return (
    <div className="space-y-8 animate-fade-in">
      <input ref={fileRef} type="file" accept=".csv" onChange={handleUpload} className="hidden" />

      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-txt-primary tracking-tight">
            Command <span className="text-gradient-besg">Center</span>
          </h1>
          <p className="text-sm text-txt-muted mt-1">Real-time ingestion pipeline health and analytics</p>
        </div>
        <button onClick={loadData} className="btn-ghost" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /><span>Refresh</span>
        </button>
      </div>

      {/* Toast */}
      {uploadResult && (
        <div className={`flex items-center gap-3 px-5 py-3.5 rounded-2xl border animate-fade-in ${
          uploadResult.ok ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
          {uploadResult.ok ? <CheckCircle2 size={18} className="text-emerald-500" /> : <XCircle size={18} className="text-red-500" />}
          <span className="text-sm font-medium text-txt-secondary">{uploadResult.msg}</span>
          <button onClick={() => setUploadResult(null)} className="ml-auto text-txt-faint hover:text-txt-secondary text-lg leading-none">×</button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-5 stagger-children">
        {[
          { label: 'Total Records', value: totalRows, icon: TrendingUp, color: 'text-besg-500', bg: 'bg-besg-50', desc: 'Canonical activity rows' },
          { label: 'Pending Review', value: totalPending, icon: Clock, color: 'text-amber-500', bg: 'bg-amber-50', desc: 'Awaiting analyst action' },
          { label: 'Anomaly Flags', value: totalFailed, icon: ShieldAlert, color: 'text-red-500', bg: 'bg-red-50', desc: 'Detected across all sources' },
          { label: 'Ingestion Jobs', value: totalJobs, icon: Activity, color: 'text-blue-500', bg: 'bg-blue-50', desc: 'Completed pipeline runs' },
        ].map((c) => (
          <div key={c.label} className="card px-6 py-5 group hover:shadow-md transition-all duration-300">
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xs font-bold uppercase tracking-widest text-txt-faint">{c.label}</span>
              <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
                <c.icon size={18} className={c.color} />
              </div>
            </div>
            <p className="stat-value">
              {loading ? <span className="shimmer inline-block w-14 h-9" /> : <AnimatedCounter target={c.value} />}
            </p>
            <p className="text-2xs text-txt-faint mt-1">{c.desc}</p>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-3 gap-5">
        {/* Scope Distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Scope Distribution</h3>
          <p className="text-2xs text-txt-faint mb-3">Records by GHG scope category</p>
          {loading ? <div className="shimmer w-full h-[180px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={scopeData} cx="50%" cy="50%" innerRadius={45} outerRadius={72} paddingAngle={3} dataKey="value"
                     animationBegin={0} animationDuration={800} animationEasing="ease-out">
                  {scopeData.map((entry, i) => <Cell key={i} fill={entry.fill} stroke="white" strokeWidth={2} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="flex items-center justify-center gap-4 mt-2">
            {scopeData.map((s) => (
              <div key={s.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.fill }} />
                <span className="text-2xs text-txt-muted font-medium">{s.name} ({s.value})</span>
              </div>
            ))}
          </div>
        </div>

        {/* Confidence Distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Confidence Distribution</h3>
          <p className="text-2xs text-txt-faint mb-3">Records by normalized confidence score</p>
          {loading ? <div className="shimmer w-full h-[180px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={confidenceData} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8E4" vertical={false} />
                <XAxis dataKey="range" tick={{ fontSize: 10, fill: '#9CA3AF', fontFamily: 'DM Sans' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} width={24} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} animationDuration={800}>
                  {confidenceData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Anomaly Breakdown */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Anomaly Severity</h3>
          <p className="text-2xs text-txt-faint mb-3">Flag distribution by severity level</p>
          {loading ? <div className="shimmer w-full h-[180px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={flagData} cx="50%" cy="50%" outerRadius={72} paddingAngle={4} dataKey="value"
                     animationBegin={200} animationDuration={800} animationEasing="ease-out">
                  {flagData.map((entry, i) => <Cell key={i} fill={entry.fill} stroke="white" strokeWidth={2} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="flex items-center justify-center gap-4 mt-2">
            {flagData.map((f) => (
              <div key={f.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: f.fill }} />
                <span className="text-2xs text-txt-muted font-medium">{f.name} ({f.value})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Emissions by Source */}
      {emissionsData.length > 0 && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-txt-primary">Emissions by Source Type</h3>
              <p className="text-2xs text-txt-faint mt-0.5">Total calculated kgCO₂e per ingestion source</p>
            </div>
            <span className="text-2xs text-txt-faint font-mono">kgCO₂e</span>
          </div>
          {loading ? <div className="shimmer w-full h-[200px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={emissionsData} layout="vertical" barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8E4" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#9CA3AF', fontFamily: 'DM Sans' }} axisLine={false} tickLine={false}
                       tickFormatter={(v: number) => v.toLocaleString()} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#374151', fontFamily: 'DM Sans', fontWeight: 600 }}
                       axisLine={false} tickLine={false} width={60} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }}
                         formatter={(value: any) => [`${Number(value).toLocaleString()} kgCO₂e`, 'Emissions']} />
                <Bar dataKey="value" radius={[0, 8, 8, 0]} animationDuration={1000}>
                  {emissionsData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Source Pipeline Cards */}
      <div>
        <h2 className="text-lg font-bold text-txt-primary mb-4">Source Pipelines</h2>
        <div className="grid grid-cols-3 gap-5 stagger-children">
          {Object.entries(SOURCE_CONFIG).map(([key, cfg]) => {
            const stat = stats.find((s) => s.source_type === key);
            return (
              <div key={key} className="card-hover overflow-hidden group">
                <div className="h-1.5 rounded-t-2xl" style={{ background: cfg.gradient }} />
                <div className="p-6">
                  <div className="flex items-center gap-4 mb-5">
                    <div className="w-12 h-12 rounded-2xl shadow-lg flex items-center justify-center group-hover:scale-105 transition-transform duration-300"
                         style={{ background: cfg.gradient }}>
                      <cfg.icon size={22} className="text-white" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-txt-primary">{cfg.label}</h3>
                      <p className="text-2xs text-txt-faint">{stat?.total_rows || 0} records ingested</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-5">
                    {[
                      { label: 'Total', value: stat?.total_rows || 0 },
                      { label: 'Pending', value: stat?.pending_review || 0 },
                      { label: 'Failed', value: stat?.failed_rows || 0 },
                      { label: 'Suspicious', value: stat?.suspicious_rows || 0 },
                    ].map((m) => (
                      <div key={m.label} className="px-3 py-2.5 rounded-xl bg-surface-secondary border border-surface-border-light">
                        <p className="text-2xs text-txt-faint mb-0.5">{m.label}</p>
                        <p className="text-sm font-bold text-txt-primary">{loading ? <span className="shimmer inline-block w-6 h-4" /> : m.value}</p>
                      </div>
                    ))}
                  </div>
                  <button onClick={() => triggerUpload(key)} disabled={uploading}
                          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold border border-surface-border 
                                   hover:border-besg-300 hover:bg-besg-50 text-txt-secondary hover:text-besg-600 transition-all duration-200 disabled:opacity-40">
                    <Upload size={14} /><span>{uploading && uploadSource === key ? 'Uploading...' : 'Upload CSV'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Jobs */}
      <div>
        <h2 className="text-lg font-bold text-txt-primary mb-4">Recent Ingestion Jobs</h2>
        <div className="card overflow-hidden">
          <table className="data-table">
            <thead><tr><th>Source</th><th>File</th><th>Status</th><th className="text-right">Total</th><th className="text-right">Parsed</th><th className="text-right">Failed</th><th>Time</th></tr></thead>
            <tbody>
              {loading ? Array.from({ length: 3 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 7 }).map((_, j) => <td key={j}><span className="shimmer inline-block w-16 h-4" /></td>)}</tr>
              )) : jobs.map((job) => (
                <tr key={job.id}>
                  <td><span className={`badge ${job.source_type === 'SAP_MM' ? 'bg-orange-50 text-orange-600 ring-1 ring-orange-200' : job.source_type === 'UTILITY_INTERVAL' ? 'bg-blue-50 text-blue-600 ring-1 ring-blue-200' : 'bg-violet-50 text-violet-600 ring-1 ring-violet-200'}`}>
                    {SOURCE_CONFIG[job.source_type as keyof typeof SOURCE_CONFIG]?.label || job.source_type}</span></td>
                  <td className="font-mono text-xs text-txt-muted">{job.file_name}</td>
                  <td><span className={`badge ${job.status === 'COMPLETE' ? 'badge-success' : job.status === 'FAILED' ? 'badge-blocking' : 'badge-warning'}`}>
                    {job.status === 'COMPLETE' && <CheckCircle2 size={10} />}{job.status}</span></td>
                  <td className="text-right font-mono font-medium">{job.total_rows}</td>
                  <td className="text-right font-mono text-emerald-600 font-medium">{job.parsed_rows}</td>
                  <td className="text-right font-mono text-red-500">{job.failed_rows || '—'}</td>
                  <td className="text-txt-faint text-xs">{new Date(job.triggered_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && jobs.length === 0 && (
            <div className="py-16 text-center"><Upload size={28} className="mx-auto mb-3 text-txt-faint" /><p className="text-txt-muted text-sm font-medium">No ingestion jobs yet</p></div>
          )}
        </div>
      </div>
    </div>
  );
}

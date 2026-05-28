import { useState, useEffect } from 'react';
import { fetchReviewQueue } from '../api/client';
import type { QueueRecord } from '../types';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  AreaChart, Area,
} from 'recharts';
import { RefreshCw, TrendingDown, AlertTriangle, Shield, Leaf } from 'lucide-react';

const SCOPE_COLORS: Record<string, string> = { SCOPE_1: '#EF4444', SCOPE_2: '#3B82F6', SCOPE_3: '#8B5CF6' };
const SOURCE_COLORS: Record<string, string> = { SAP_MM: '#EA580C', UTILITY_INTERVAL: '#2563EB', TRAVEL_CONCUR: '#7C3AED' };
const SOURCE_LABELS: Record<string, string> = { SAP_MM: 'SAP MM', UTILITY_INTERVAL: 'Utility', TRAVEL_CONCUR: 'Travel' };

export default function Analytics() {
  const [records, setRecords] = useState<QueueRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { const r = await fetchReviewQueue({ page_size: '100' }); setRecords(r.results || []); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  // ── Analytics computations ──
  const totalEmissions = records.reduce((s, r) => s + (r.calculated_emissions ? parseFloat(r.calculated_emissions) : 0), 0);
  const avgConfidence = records.length > 0 ? records.reduce((s, r) => s + parseFloat(r.confidence_score), 0) / records.length : 0;
  const totalFlags = records.reduce((s, r) => s + r.anomaly_summary.length, 0);
  const approvedCount = records.filter(r => r.review_status === 'APPROVED').length;
  const approvalRate = records.length > 0 ? (approvedCount / records.length * 100) : 0;

  // Emissions by scope
  const emissionsByScope: Record<string, number> = {};
  records.forEach(r => { if (r.calculated_emissions && r.scope_category) emissionsByScope[r.scope_category] = (emissionsByScope[r.scope_category] || 0) + parseFloat(r.calculated_emissions); });
  const scopeEmissions = Object.entries(emissionsByScope).map(([k, v]) => ({ name: k.replace('_', ' '), value: Math.round(v), fill: SCOPE_COLORS[k] || '#9CA3AF' }));

  // Activity type distribution (top 8)
  const activityCounts: Record<string, number> = {};
  records.forEach(r => { if (r.activity_type) activityCounts[r.activity_type] = (activityCounts[r.activity_type] || 0) + 1; });
  const activityData = Object.entries(activityCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 8)
    .map(([name, count]) => ({ name: name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), count }));

  // Radar: data quality by source
  const radarData = Object.keys(SOURCE_COLORS).map(src => {
    const srcRecords = records.filter(r => r.source_type === src);
    const avgConf = srcRecords.length > 0 ? srcRecords.reduce((s, r) => s + parseFloat(r.confidence_score), 0) / srcRecords.length * 100 : 0;
    const cleanRate = srcRecords.length > 0 ? srcRecords.filter(r => r.anomaly_summary.length === 0).length / srcRecords.length * 100 : 0;
    const coverage = srcRecords.length > 0 ? srcRecords.filter(r => r.normalized_quantity).length / srcRecords.length * 100 : 0;
    return { source: SOURCE_LABELS[src] || src, confidence: Math.round(avgConf), cleanliness: Math.round(cleanRate), coverage: Math.round(coverage) };
  });

  // Confidence trend (simulated over records sorted by date)
  const sorted = [...records].sort((a, b) => (a.activity_date || '').localeCompare(b.activity_date || ''));
  const trendData: { date: string; confidence: number; emissions: number }[] = [];
  let runningConf = 0, count = 0;
  sorted.forEach((r, i) => {
    runningConf += parseFloat(r.confidence_score) * 100; count++;
    if (i % 5 === 4 || i === sorted.length - 1) {
      trendData.push({
        date: r.activity_date || `Record ${i + 1}`,
        confidence: Math.round(runningConf / count),
        emissions: r.calculated_emissions ? Math.round(parseFloat(r.calculated_emissions)) : 0,
      });
    }
  });

  // Status breakdown
  const statusCounts: Record<string, number> = {};
  records.forEach(r => statusCounts[r.review_status] = (statusCounts[r.review_status] || 0) + 1);
  const statusData = Object.entries(statusCounts).map(([name, value]) => ({
    name: name.replace('_', ' '),
    value,
    fill: name === 'APPROVED' ? '#10B981' : name === 'REJECTED' ? '#EF4444' : name === 'PENDING' ? '#F59E0B' : name === 'AUDIT_LOCKED' ? '#8B5CF6' : '#6B7280',
  }));

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-txt-primary tracking-tight">
            ESG <span className="text-gradient-besg">Analytics</span>
          </h1>
          <p className="text-sm text-txt-muted mt-1">Deep insights across your ingested activity data</p>
        </div>
        <button onClick={load} className="btn-ghost" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /><span>Refresh</span>
        </button>
      </div>

      {/* Headline KPIs */}
      <div className="grid grid-cols-4 gap-5 stagger-children">
        {[
          { label: 'Total Emissions', value: `${Math.round(totalEmissions).toLocaleString()}`, unit: 'kgCO₂e', icon: Leaf, color: 'text-besg-500', bg: 'bg-besg-50' },
          { label: 'Avg Confidence', value: `${(avgConfidence * 100).toFixed(1)}%`, unit: '', icon: TrendingDown, color: 'text-blue-500', bg: 'bg-blue-50' },
          { label: 'Total Flags', value: `${totalFlags}`, unit: 'detected', icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50' },
          { label: 'Approval Rate', value: `${approvalRate.toFixed(0)}%`, unit: `${approvedCount}/${records.length}`, icon: Shield, color: 'text-emerald-500', bg: 'bg-emerald-50' },
        ].map(c => (
          <div key={c.label} className="card px-6 py-5 group hover:shadow-md transition-all duration-300">
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xs font-bold uppercase tracking-widest text-txt-faint">{c.label}</span>
              <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
                <c.icon size={18} className={c.color} />
              </div>
            </div>
            <p className="stat-value text-2xl">{loading ? <span className="shimmer inline-block w-16 h-7" /> : c.value}</p>
            {c.unit && <p className="text-2xs text-txt-faint mt-0.5">{c.unit}</p>}
          </div>
        ))}
      </div>

      {/* Row: Emissions by Scope + Confidence Trend */}
      <div className="grid grid-cols-2 gap-5">
        <div className="card p-6">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Emissions by Scope</h3>
          <p className="text-2xs text-txt-faint mb-4">kgCO₂e distribution across GHG scopes</p>
          {loading ? <div className="shimmer w-full h-[220px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={scopeEmissions} cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={4} dataKey="value"
                     label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                     animationDuration={1000}>
                  {scopeEmissions.map((e, i) => <Cell key={i} fill={e.fill} stroke="white" strokeWidth={2} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }}
                         formatter={(v: any) => [`${Number(v).toLocaleString()} kgCO₂e`, 'Emissions']} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-6">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Confidence Trend</h3>
          <p className="text-2xs text-txt-faint mb-4">Rolling average confidence across records</p>
          {loading ? <div className="shimmer w-full h-[220px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2E9844" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#2E9844" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8E4" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} width={30} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
                <Area type="monotone" dataKey="confidence" stroke="#2E9844" strokeWidth={2} fill="url(#confGrad)" animationDuration={1200} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Row: Data Quality Radar + Activity Distribution + Status */}
      <div className="grid grid-cols-3 gap-5">
        <div className="card p-6">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Data Quality Radar</h3>
          <p className="text-2xs text-txt-faint mb-4">Quality metrics per source type</p>
          {loading ? <div className="shimmer w-full h-[220px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={80}>
                <PolarGrid stroke="#E2E8E4" />
                <PolarAngleAxis dataKey="source" tick={{ fontSize: 11, fill: '#374151', fontFamily: 'DM Sans', fontWeight: 600 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9, fill: '#9CA3AF' }} />
                <Radar name="Confidence" dataKey="confidence" stroke="#2E9844" fill="#2E9844" fillOpacity={0.15} strokeWidth={2} animationDuration={1000} />
                <Radar name="Cleanliness" dataKey="cleanliness" stroke="#0bafd0" fill="#0bafd0" fillOpacity={0.1} strokeWidth={2} animationDuration={1200} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-6">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Activity Types</h3>
          <p className="text-2xs text-txt-faint mb-4">Top activity categories by record count</p>
          {loading ? <div className="shimmer w-full h-[220px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={activityData} layout="vertical" barCategoryGap="15%">
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8E4" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 9, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: '#374151', fontFamily: 'DM Sans' }} axisLine={false} tickLine={false} width={90} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
                <Bar dataKey="count" fill="#2E9844" radius={[0, 6, 6, 0]} animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card p-6">
          <h3 className="text-sm font-bold text-txt-primary mb-1">Review Status</h3>
          <p className="text-2xs text-txt-faint mb-4">Records by current workflow status</p>
          {loading ? <div className="shimmer w-full h-[220px] rounded-xl" /> : (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value"
                     animationDuration={900}>
                  {statusData.map((e, i) => <Cell key={i} fill={e.fill} stroke="white" strokeWidth={2} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8E4', fontSize: '12px', fontFamily: 'DM Sans' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
            {statusData.map(s => (
              <div key={s.name} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.fill }} />
                <span className="text-2xs text-txt-muted font-medium">{s.name} ({s.value})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

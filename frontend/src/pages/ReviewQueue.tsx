import { useState, useEffect, useCallback } from 'react';
import { fetchReviewQueue } from '../api/client';
import type { QueueRecord, PaginatedResponse } from '../types';
import ProvenanceDrawer from './ProvenanceDrawer';
import {
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  ShieldAlert,
  Info,
} from 'lucide-react';

const SCOPE_LABELS: Record<string, { label: string; cls: string }> = {
  SCOPE_1: { label: 'Scope 1', cls: 'badge-scope1' },
  SCOPE_2: { label: 'Scope 2', cls: 'badge-scope2' },
  SCOPE_3: { label: 'Scope 3', cls: 'badge-scope3' },
};

const STATUS_STYLES: Record<string, string> = {
  PENDING: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  UNDER_REVIEW: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  REJECTED: 'bg-red-50 text-red-700 ring-1 ring-red-200',
  AUDIT_LOCKED: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
};

const SOURCE_LABELS: Record<string, string> = {
  SAP_MM: 'SAP MM', UTILITY_INTERVAL: 'Utility', TRAVEL_CONCUR: 'Travel',
};

export default function ReviewQueue() {
  const [data, setData] = useState<PaginatedResponse<QueueRecord> | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sourceFilter, setSourceFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [reviewOnly, setReviewOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page) };
    if (sourceFilter) params.source_type = sourceFilter;
    if (scopeFilter) params.scope_category = scopeFilter;
    if (statusFilter) params.review_status = statusFilter;
    if (priorityFilter) params.review_priority = priorityFilter;
    if (reviewOnly) params.requires_review = 'true';
    try { const res = await fetchReviewQueue(params); setData(res); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [page, sourceFilter, scopeFilter, statusFilter, priorityFilter, reviewOnly]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDrawerClose = () => { setSelectedId(null); loadData(); };

  const getConfidenceColor = (s: number) => s >= 0.85 ? 'bg-emerald-500' : s >= 0.6 ? 'bg-blue-500' : s >= 0.35 ? 'bg-amber-500' : 'bg-red-500';
  const getPriorityClass = (p: string) => ({ CRITICAL: 'priority-critical', HIGH: 'priority-high', MEDIUM: 'priority-medium', LOW: 'priority-low' }[p] || 'priority-low');

  const totalPages = data ? Math.ceil(data.count / 25) : 0;

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-txt-primary">
            Analyst <span className="text-gradient-besg">Review Queue</span>
          </h1>
          <p className="text-sm text-txt-muted mt-1">
            {data ? `${data.count} records` : '—'} • Sorted by confidence score (worst first)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowFilters(!showFilters)} className={`btn-ghost ${showFilters ? 'text-besg-600 bg-besg-50' : ''}`}>
            <Filter size={14} /><span>Filters</span>
          </button>
          <button onClick={loadData} className="btn-ghost" disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="card px-5 py-4 flex items-center gap-3 flex-wrap animate-fade-in">
          <select value={sourceFilter} onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }} className="select">
            <option value="">All Sources</option>
            <option value="SAP_MM">SAP MM</option>
            <option value="UTILITY_INTERVAL">Utility</option>
            <option value="TRAVEL_CONCUR">Travel</option>
          </select>
          <select value={scopeFilter} onChange={(e) => { setScopeFilter(e.target.value); setPage(1); }} className="select">
            <option value="">All Scopes</option>
            <option value="SCOPE_1">Scope 1</option>
            <option value="SCOPE_2">Scope 2</option>
            <option value="SCOPE_3">Scope 3</option>
          </select>
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="select">
            <option value="">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
          <select value={priorityFilter} onChange={(e) => { setPriorityFilter(e.target.value); setPage(1); }} className="select">
            <option value="">All Priorities</option>
            <option value="CRITICAL">🔴 Critical</option>
            <option value="HIGH">🟠 High</option>
            <option value="MEDIUM">🔵 Medium</option>
            <option value="LOW">⚪ Low</option>
          </select>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-txt-muted hover:text-txt-primary transition-colors">
            <input type="checkbox" checked={reviewOnly} onChange={(e) => { setReviewOnly(e.target.checked); setPage(1); }}
                   className="w-4 h-4 rounded border-gray-300 text-besg-500 focus:ring-besg-200" />
            <span>Needs review</span>
          </label>
          {(sourceFilter || scopeFilter || statusFilter || priorityFilter || reviewOnly) && (
            <button onClick={() => { setSourceFilter(''); setScopeFilter(''); setStatusFilter(''); setPriorityFilter(''); setReviewOnly(false); setPage(1); }}
                    className="text-xs text-txt-faint hover:text-red-500 transition-colors ml-auto font-medium">Clear all</button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th className="w-8"></th>
                <th>Source</th>
                <th>Scope</th>
                <th>Activity</th>
                <th>Date</th>
                <th className="text-right">Quantity</th>
                <th>Confidence</th>
                <th>Flags</th>
                <th>Status</th>
                <th className="text-right">Emissions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 10 }).map((_, j) => (<td key={j}><span className="shimmer inline-block w-14 h-4" /></td>))}</tr>
              )) : data?.results.map((r) => {
                const score = parseFloat(r.confidence_score);
                return (
                  <tr key={r.id} onClick={() => setSelectedId(r.id)} className="cursor-pointer group">
                    <td className="pr-0"><div className={`priority-dot ${getPriorityClass(r.review_priority)}`} /></td>
                    <td><span className="text-xs font-semibold text-txt-secondary">{SOURCE_LABELS[r.source_type] || r.source_type}</span></td>
                    <td>{r.scope_category ? <span className={`badge ${SCOPE_LABELS[r.scope_category]?.cls || ''}`}>{SCOPE_LABELS[r.scope_category]?.label}</span> : <span className="text-txt-faint">—</span>}</td>
                    <td><span className="text-xs text-txt-muted">{r.activity_type?.replace(/_/g, ' ') || '—'}</span></td>
                    <td><span className="text-xs text-txt-faint font-mono">{r.activity_date || '—'}</span></td>
                    <td className="text-right">
                      <span className="text-xs font-mono text-txt-secondary font-medium">
                        {r.normalized_quantity ? parseFloat(r.normalized_quantity).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—'}
                      </span>
                      {r.normalized_unit && <span className="text-2xs text-txt-faint ml-1">{r.normalized_unit}</span>}
                    </td>
                    <td>
                      <div className="flex items-center gap-2 min-w-[90px]">
                        <div className="confidence-bar flex-1">
                          <div className={`confidence-fill ${getConfidenceColor(score)}`} style={{ width: `${Math.max(score * 100, 3)}%` }} />
                        </div>
                        <span className="text-2xs font-mono text-txt-faint w-8 text-right font-medium">{(score * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center gap-1">
                        {r.blocking_count > 0 && <span className="badge badge-blocking"><ShieldAlert size={10} />{r.blocking_count}</span>}
                        {r.warning_count > 0 && <span className="badge badge-warning"><AlertTriangle size={10} />{r.warning_count}</span>}
                        {r.blocking_count === 0 && r.warning_count === 0 && r.anomaly_summary.length > 0 && <span className="badge badge-info"><Info size={10} />{r.anomaly_summary.length}</span>}
                        {r.anomaly_summary.length === 0 && <span className="text-txt-faint text-2xs font-medium">clean ✓</span>}
                      </div>
                    </td>
                    <td><span className={`badge ${STATUS_STYLES[r.review_status] || ''}`}>{r.review_status.replace('_', ' ')}</span></td>
                    <td className="text-right">
                      <span className="text-xs font-mono text-txt-secondary font-medium">
                        {r.calculated_emissions ? `${parseFloat(r.calculated_emissions).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                      </span>
                      {r.calculated_emissions && <span className="text-2xs text-txt-faint ml-1">kg</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {!loading && data?.results.length === 0 && (
          <div className="py-20 text-center">
            <Filter size={36} className="mx-auto mb-3 text-gray-300" />
            <p className="text-txt-muted text-sm font-medium">No records match your filters</p>
            <p className="text-txt-faint text-xs mt-1">Try adjusting or clearing filters above</p>
          </div>
        )}

        {data && data.count > 0 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-surface-border-light bg-surface-secondary/50">
            <span className="text-xs text-txt-faint">Showing {Math.min((page - 1) * 25 + 1, data.count)}–{Math.min(page * 25, data.count)} of {data.count}</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={!data.previous} className="btn-ghost px-2 disabled:opacity-30"><ChevronLeft size={14} /></button>
              <span className="text-xs text-txt-muted px-3 font-medium">{page} / {totalPages}</span>
              <button onClick={() => setPage(page + 1)} disabled={!data.next} className="btn-ghost px-2 disabled:opacity-30"><ChevronRight size={14} /></button>
            </div>
          </div>
        )}
      </div>

      {selectedId && <ProvenanceDrawer recordId={selectedId} onClose={handleDrawerClose} />}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { fetchRecordDetail, approveRecord, rejectRecord, resolveFlag, getDecodedToken } from '../api/client';
import type { RecordDetail, NormalizationEvent, AnomalyFlag } from '../types';
import {
  X, CheckCircle2, XCircle, Clock, Shield, ShieldAlert, AlertTriangle, Info,
  ArrowRight, FileText, Layers, Flag, History, Cpu, User, Lock, Hash,
} from 'lucide-react';

interface Props { recordId: string; onClose: () => void; }
type Tab = 'overview' | 'raw' | 'timeline' | 'flags' | 'history';

const SEV: Record<string, { badge: string; icon: typeof ShieldAlert }> = {
  BLOCKING: { badge: 'badge-blocking', icon: ShieldAlert },
  WARNING: { badge: 'badge-warning', icon: AlertTriangle },
  INFO: { badge: 'badge-info', icon: Info },
};

export default function ProvenanceDrawer({ recordId, onClose }: Props) {
  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('overview');
  const [actionLoading, setActionLoading] = useState(false);
  const [notes, setNotes] = useState('');
  const [flagNote, setFlagNote] = useState('');
  const [actionResult, setActionResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const userRole = getDecodedToken()?.role || 'VIEWER';
  const canWrite = userRole === 'ANALYST' || userRole === 'ADMIN';

  useEffect(() => { load(); }, [recordId]);

  const load = async () => {
    setLoading(true);
    try { setRecord(await fetchRecordDetail(recordId)); } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleApprove = async () => {
    setActionLoading(true);
    try { await approveRecord(recordId, notes); setActionResult({ ok: true, msg: 'Record approved' }); load(); }
    catch (e: any) { setActionResult({ ok: false, msg: e.response?.data?.error || 'Failed' }); }
    finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    if (!notes.trim()) { setActionResult({ ok: false, msg: 'Notes required for rejection' }); return; }
    setActionLoading(true);
    try { await rejectRecord(recordId, notes); setActionResult({ ok: true, msg: 'Record rejected' }); load(); }
    catch (e: any) { setActionResult({ ok: false, msg: e.response?.data?.error || 'Failed' }); }
    finally { setActionLoading(false); }
  };

  const handleResolveFlag = async (flagId: string) => {
    if (!flagNote.trim()) return;
    try { await resolveFlag(flagId, flagNote); setFlagNote(''); load(); }
    catch (e) { console.error(e); }
  };

  const TABS: { key: Tab; label: string; icon: typeof FileText; count?: number }[] = [
    { key: 'overview', label: 'Overview', icon: Layers },
    { key: 'raw', label: 'Raw Payload', icon: FileText },
    { key: 'timeline', label: 'Transformations', icon: History, count: record?.normalization_events.length },
    { key: 'flags', label: 'Anomaly Flags', icon: Flag, count: record?.anomaly_flags.length },
    { key: 'history', label: 'Review History', icon: Shield, count: record?.review_events.length },
  ];

  return (
    <>
      <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-50" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-[700px] bg-white border-l border-surface-border z-50 flex flex-col animate-slide-in shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border flex-shrink-0">
          <div>
            <h2 className="text-lg font-bold text-txt-primary">Record Provenance</h2>
            {record && <p className="text-xs text-txt-faint font-mono mt-0.5">{record.id.slice(0, 8)}… • {record.source_type}</p>}
          </div>
          <button onClick={onClose} className="btn-ghost px-2"><X size={18} /></button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-0.5 px-6 pt-2 border-b border-surface-border flex-shrink-0 overflow-x-auto">
          {TABS.map((t) => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-semibold border-b-2 transition-all whitespace-nowrap
                ${tab === t.key ? 'border-besg-500 text-besg-600' : 'border-transparent text-txt-faint hover:text-txt-secondary'}`}>
              <t.icon size={13} /><span>{t.label}</span>
              {t.count !== undefined && t.count > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-surface-secondary text-2xs text-txt-faint font-semibold">{t.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? <div className="space-y-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="shimmer h-14 rounded-xl" />)}</div>
          : record ? <>
            {tab === 'overview' && <OverviewTab record={record} />}
            {tab === 'raw' && <RawPayloadTab record={record} />}
            {tab === 'timeline' && <TimelineTab events={record.normalization_events} />}
            {tab === 'flags' && <FlagsTab flags={record.anomaly_flags} flagNote={flagNote} setFlagNote={setFlagNote} onResolve={handleResolveFlag} canWrite={canWrite} />}
            {tab === 'history' && <HistoryTab events={record.review_events} />}
          </> : <div className="text-center py-12 text-txt-faint">Failed to load</div>}
        </div>

        {/* Action bar — only for ANALYST and ADMIN */}
        {canWrite && record && !['APPROVED', 'AUDIT_LOCKED', 'REJECTED'].includes(record.review_status) && (
          <div className="border-t border-surface-border px-6 py-4 flex-shrink-0 space-y-3 bg-surface-secondary/50">
            {actionResult && (
              <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium animate-fade-in ${
                actionResult.ok ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'
              }`}>{actionResult.ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}{actionResult.msg}</div>
            )}
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Review notes (required for reject)..." className="input h-16 resize-none text-xs" />
            <div className="flex items-center gap-3">
              <button onClick={handleApprove} disabled={actionLoading} className="btn-primary flex-1"><CheckCircle2 size={14} />Approve</button>
              <button onClick={handleReject} disabled={actionLoading} className="btn-danger flex-1"><XCircle size={14} />Reject</button>
            </div>
          </div>
        )}

        {record && record.review_status === 'AUDIT_LOCKED' && (
          <div className="border-t border-surface-border px-6 py-4 flex-shrink-0">
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-violet-50 border border-violet-200">
              <Lock size={14} className="text-violet-500" /><span className="text-xs text-violet-700 font-semibold">Audit-locked — cannot be modified</span>
            </div>
          </div>
        )}
        {/* Read-only notice for VIEWER */}
        {!canWrite && record && !['APPROVED', 'AUDIT_LOCKED', 'REJECTED'].includes(record.review_status) && (
          <div className="border-t border-surface-border px-6 py-4 flex-shrink-0">
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200">
              <Lock size={14} className="text-amber-500" /><span className="text-xs text-amber-700 font-semibold">Read-only — VIEWER role cannot approve or reject records</span>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function OverviewTab({ record }: { record: RecordDetail }) {
  const score = parseFloat(record.confidence_score);
  const sections = [
    { title: 'Classification', items: [
      { label: 'Source Type', value: record.source_type },
      { label: 'Activity', value: record.activity_type?.replace(/_/g, ' ') || '—' },
      { label: 'Scope', value: record.scope_category || '—' },
      { label: 'Subcategory', value: record.scope_subcategory || '—' },
      { label: 'GHG Protocol', value: record.ghg_protocol_category || '—' },
    ]},
    { title: 'Quantity', items: [
      { label: 'Raw', value: `${record.raw_quantity_string || '—'} ${record.raw_unit}` },
      { label: 'Normalized', value: record.normalized_quantity ? `${parseFloat(record.normalized_quantity).toLocaleString('en-IN', { maximumFractionDigits: 4 })} ${record.normalized_unit}` : '—' },
    ]},
    { title: 'Emissions', items: [
      { label: 'Calculated', value: record.calculated_emissions ? `${parseFloat(record.calculated_emissions).toLocaleString('en-IN', { maximumFractionDigits: 4 })} kgCO2e` : '—' },
      { label: 'Factor', value: record.emission_factor_value ? `${record.emission_factor_value} ${record.emission_factor_unit}` : '—' },
    ]},
    { title: 'Context', items: [
      { label: 'Facility', value: record.facility_id || '—' }, { label: 'Cost Center', value: record.cost_center || '—' },
      { label: 'Supplier', value: record.supplier_id || '—' }, { label: 'Material Group', value: record.material_group || '—' },
      { label: 'Document Ref', value: record.source_document_ref || '—' }, { label: 'Date', value: record.activity_date || '—' },
    ]},
  ];

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="flex items-center gap-5 p-5 rounded-2xl bg-surface-secondary border border-surface-border">
        <div className="flex-1">
          <p className="text-2xs font-bold uppercase tracking-widest text-txt-faint mb-1">Confidence Score</p>
          <div className="flex items-center gap-3">
            <span className="text-4xl font-extrabold text-txt-primary">{(score * 100).toFixed(0)}%</span>
            <div className="flex-1"><div className="confidence-bar h-2.5"><div className={`confidence-fill ${score >= 0.85 ? 'bg-emerald-500' : score >= 0.6 ? 'bg-blue-500' : score >= 0.35 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${Math.max(score * 100, 3)}%` }} /></div></div>
          </div>
          <p className="text-2xs text-txt-faint mt-1">Priority: <span className={`font-bold ${record.review_priority === 'CRITICAL' ? 'text-red-500' : record.review_priority === 'HIGH' ? 'text-amber-500' : record.review_priority === 'MEDIUM' ? 'text-blue-500' : 'text-gray-400'}`}>{record.review_priority}</span></p>
        </div>
        <span className={`badge text-xs px-3 py-1 ${record.review_status === 'APPROVED' ? 'badge-success' : record.review_status === 'REJECTED' ? 'badge-blocking' : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'}`}>{record.review_status.replace('_', ' ')}</span>
      </div>

      <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-surface-secondary border border-surface-border-light">
        <Hash size={12} className="text-txt-faint" /><span className="text-2xs text-txt-faint">Immutable Hash:</span>
        <code className="text-2xs font-mono text-txt-muted truncate">{record.immutable_hash}</code>
      </div>

      {sections.map((s) => (
        <div key={s.title}>
          <h3 className="text-xs font-bold uppercase tracking-widest text-txt-faint mb-3">{s.title}</h3>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {s.items.map((item) => (<div key={item.label} className="py-1.5"><p className="text-2xs text-txt-faint mb-0.5">{item.label}</p><p className="text-sm text-txt-primary font-medium">{item.value}</p></div>))}
          </div>
        </div>
      ))}

      {record.normalization_rules.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-txt-faint mb-3">Applied Rules</h3>
          <div className="flex flex-wrap gap-1.5">
            {record.normalization_rules.map((r, i) => <span key={i} className="badge bg-surface-secondary text-txt-muted ring-1 ring-surface-border font-mono">{r}</span>)}
          </div>
        </div>
      )}
    </div>
  );
}

function RawPayloadTab({ record }: { record: RecordDetail }) {
  const payload = record.raw_payload;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2"><Lock size={12} className="text-txt-faint" /><span className="text-2xs text-txt-faint uppercase tracking-widest font-bold">Immutable source payload — exactly as received</span></div>
      {payload ? (
        <div className="rounded-2xl border border-surface-border overflow-hidden">
          <div className="px-5 py-3 border-b border-surface-border bg-surface-secondary flex items-center justify-between">
            <span className="text-2xs text-txt-faint">Row #{payload.row_number} • {new Date(payload.received_at).toLocaleString()}</span>
            <code className="text-2xs text-txt-faint font-mono">{payload.immutable_hash?.slice(0, 16)}…</code>
          </div>
          <div className="p-5 space-y-1">
            {Object.entries(payload.raw_payload).map(([k, v]) => (
              <div key={k} className="flex items-start gap-4 py-1.5 border-b border-surface-border-light last:border-0">
                <span className="text-2xs font-mono text-txt-faint w-36 flex-shrink-0 text-right pt-0.5 font-medium">{k}</span>
                <span className="text-xs font-mono text-txt-primary break-all">{String(v) || <span className="text-txt-faint italic">empty</span>}</span>
              </div>
            ))}
          </div>
        </div>
      ) : <div className="text-center py-12 text-txt-faint text-sm">Not available</div>}
    </div>
  );
}

function TimelineTab({ events }: { events: NormalizationEvent[] }) {
  return (
    <div className="space-y-1">
      <p className="text-2xs text-txt-faint mb-4 font-medium">{events.length} transformation{events.length !== 1 ? 's' : ''} — chronological order</p>
      {events.length === 0 ? <div className="text-center py-12 text-txt-faint text-sm">No events</div> : (
        <div className="space-y-0">
          {events.map((e, i) => (
            <div key={e.id} className="flex gap-3 group">
              <div className="flex flex-col items-center flex-shrink-0 pt-1.5">
                <div className={`w-3 h-3 rounded-full flex-shrink-0 border-2 border-white shadow-sm ${e.applied_by === 'ANALYST' ? 'bg-besg-500' : 'bg-gray-300'}`} />
                {i < events.length - 1 && <div className="w-px flex-1 bg-surface-border my-0.5" />}
              </div>
              <div className="flex-1 pb-3">
                <div className="rounded-xl border border-surface-border-light p-3.5 group-hover:border-surface-border transition-colors bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <span className="badge bg-surface-secondary text-txt-muted ring-1 ring-surface-border font-mono">{e.event_type.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-1.5 text-2xs text-txt-faint">
                      {e.applied_by === 'ANALYST' ? <User size={10} className="text-besg-500" /> : <Cpu size={10} />}
                      <span>{e.applied_by}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs font-mono text-txt-muted px-2 py-0.5 rounded-lg bg-surface-secondary">{e.field_name}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <code className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-lg max-w-[200px] truncate font-mono">{e.before_value || '∅'}</code>
                    <ArrowRight size={12} className="text-txt-faint flex-shrink-0" />
                    <code className="text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-lg max-w-[200px] truncate font-mono">{e.after_value || '∅'}</code>
                  </div>
                  {e.rule_applied && <p className="text-2xs text-txt-faint font-mono mt-2">rule: {e.rule_applied}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FlagsTab({ flags, flagNote, setFlagNote, onResolve, canWrite }: { flags: AnomalyFlag[]; flagNote: string; setFlagNote: (v: string) => void; onResolve: (id: string) => void; canWrite: boolean }) {
  const open = flags.filter((f) => f.resolution_status === 'OPEN');
  const resolved = flags.filter((f) => f.resolution_status !== 'OPEN');
  return (
    <div className="space-y-5">
      {open.length > 0 && <div>
        <p className="text-xs font-bold text-txt-secondary mb-3">Open Flags ({open.length})</p>
        <div className="space-y-3">
          {open.map((f) => { const s = SEV[f.severity]; const Icon = s?.icon || Info; return (
            <div key={f.id} className="rounded-2xl border border-surface-border p-5 bg-white">
              <div className="flex items-center justify-between mb-2">
                <span className={`badge ${s?.badge || 'badge-info'}`}><Icon size={10} />{f.severity}</span>
                <span className="text-2xs text-txt-faint">{new Date(f.detected_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
              </div>
              <p className="text-sm text-txt-primary font-semibold mb-3">{f.flag_type.replace(/_/g, ' ')}</p>
              {f.severity === 'BLOCKING' && canWrite && (
                <div className="space-y-2">
                  <input type="text" value={flagNote} onChange={(e) => setFlagNote(e.target.value)} placeholder="Resolution note..." className="input text-xs" />
                  <button onClick={() => onResolve(f.id)} className="btn-ghost text-xs text-besg-600 font-semibold">✓ Resolve Flag</button>
                </div>
              )}
            </div>
          );})}
        </div>
      </div>}
      {resolved.length > 0 && <div>
        <p className="text-xs font-bold text-txt-secondary mb-3">Resolved ({resolved.length})</p>
        <div className="space-y-2">{resolved.map((f) => (
          <div key={f.id} className="rounded-xl border border-surface-border-light p-3.5 bg-surface-secondary/50">
            <div className="flex items-center justify-between">
              <span className="text-xs text-txt-muted">{f.flag_type.replace(/_/g, ' ')}</span>
              <span className="badge badge-success">{f.resolution_status.replace(/_/g, ' ')}</span>
            </div>
            {f.resolution_note && <p className="text-2xs text-txt-faint mt-1">{f.resolution_note}</p>}
          </div>
        ))}</div>
      </div>}
      {flags.length === 0 && <div className="text-center py-14"><CheckCircle2 size={28} className="mx-auto mb-2 text-emerald-400" /><p className="text-txt-muted text-sm font-medium">No anomaly flags — record is clean</p></div>}
    </div>
  );
}

function HistoryTab({ events }: { events: import('../types').ReviewEvent[] }) {
  return (
    <div className="space-y-3">
      {events.length === 0 ? <div className="text-center py-14"><Clock size={28} className="mx-auto mb-2 text-gray-300" /><p className="text-txt-muted text-sm font-medium">No review actions yet</p></div>
      : events.map((e) => (
        <div key={e.id} className="rounded-2xl border border-surface-border p-5 bg-white">
          <div className="flex items-center justify-between mb-2">
            <span className={`badge ${e.action === 'APPROVE' ? 'badge-success' : e.action === 'REJECT' ? 'badge-blocking' : 'badge-warning'}`}>{e.action.replace(/_/g, ' ')}</span>
            <span className="text-2xs text-txt-faint">{new Date(e.performed_at).toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-txt-muted mb-1">
            <span>{e.previous_status}</span><ArrowRight size={10} /><span className="font-bold text-txt-primary">{e.new_status}</span>
          </div>
          {e.performed_by_email && <p className="text-2xs text-txt-faint">by {e.performed_by_email}</p>}
          {e.notes && <p className="text-xs text-txt-muted mt-2 px-4 py-2.5 rounded-xl bg-surface-secondary border-l-3 border-besg-300">{e.notes}</p>}
        </div>
      ))}
    </div>
  );
}

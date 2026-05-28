import { useState, useRef } from 'react';
import { uploadFile } from '../api/client';
import { Upload, FileSpreadsheet, Zap, Plane, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

const SOURCES = [
  {
    key: 'SAP_MM', label: 'SAP MM Export',
    description: 'Material Management flat file — MB51 ALV-grid CSV. Handles trailing minus, European number formats, leading zero truncation, and multilingual headers.',
    icon: FileSpreadsheet, gradient: 'linear-gradient(135deg, #EA580C 0%, #F59E0B 100%)',
    features: ['Trailing minus normalization', 'European number format', 'Movement type → scope mapping', 'Leading zero restoration'],
  },
  {
    key: 'UTILITY_INTERVAL', label: 'Utility Interval',
    description: 'Smart meter 15-minute interval data. Handles MWh→kWh conversion, active export exclusion, reactive power filtering, and gap detection.',
    icon: Zap, gradient: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
    features: ['MWh → kWh unit shift', 'Reactive power exclusion', 'Active export detection', 'Interval gap analysis'],
  },
  {
    key: 'TRAVEL_CONCUR', label: 'Travel (Concur/Navan)',
    description: 'Segment-level flight booking data. Computes Haversine great-circle distance, applies cabin class multipliers, and detects duplicate segments.',
    icon: Plane, gradient: 'linear-gradient(135deg, #7C3AED 0%, #A855F7 100%)',
    features: ['Haversine distance calculation', 'Cabin class multiplier', 'Airport code enrichment', 'Status filter (flown only)'],
  },
];

export default function UploadPage() {
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; data: any } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedSource) return;
    setUploading(true); setResult(null);
    try { const job = await uploadFile(file, selectedSource); setResult({ ok: true, data: job }); }
    catch (err: any) { setResult({ ok: false, data: err.response?.data?.error || 'Upload failed' }); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-4xl">
      <div>
        <h1 className="text-3xl font-extrabold text-txt-primary">
          Data <span className="text-gradient-besg">Ingestion</span>
        </h1>
        <p className="text-sm text-txt-muted mt-1">Select a source type and upload a CSV file. The parser will normalize records and detect anomalies automatically.</p>
      </div>

      <input ref={fileRef} type="file" accept=".csv" onChange={handleUpload} className="hidden" />

      <div className="space-y-4">
        {SOURCES.map((src) => {
          const isSelected = selectedSource === src.key;
          return (
            <div key={src.key} onClick={() => setSelectedSource(src.key)}
                 className={`card-hover p-6 cursor-pointer ${isSelected ? 'ring-2 ring-besg-400 border-besg-300' : ''}`}>
              <div className="flex items-start gap-5">
                <div className="w-14 h-14 rounded-2xl shadow-lg flex items-center justify-center flex-shrink-0" style={{ background: src.gradient }}>
                  <src.icon size={26} className="text-white" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-txt-primary">{src.label}</h3>
                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                      isSelected ? 'border-besg-500 bg-besg-500' : 'border-gray-300'}`}>
                      {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-white" />}
                    </div>
                  </div>
                  <p className="text-sm text-txt-muted mt-1 leading-relaxed">{src.description}</p>
                  <div className="flex flex-wrap gap-2 mt-4">
                    {src.features.map((f) => (
                      <span key={f} className="badge bg-surface-secondary text-txt-muted ring-1 ring-surface-border">{f}</span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selectedSource && (
        <button onClick={() => fileRef.current?.click()} disabled={uploading} className="btn-primary w-full py-3.5 text-base">
          {uploading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Upload size={18} />}
          <span>{uploading ? 'Processing...' : 'Upload CSV File'}</span>
          {!uploading && <ArrowRight size={18} />}
        </button>
      )}

      {result && (
        <div className={`card p-6 animate-fade-in ${result.ok ? 'border-emerald-200' : 'border-red-200'}`}>
          <div className="flex items-center gap-3 mb-4">
            {result.ok ? <CheckCircle2 size={22} className="text-emerald-500" /> : <XCircle size={22} className="text-red-500" />}
            <h3 className="text-lg font-bold text-txt-primary">{result.ok ? 'Ingestion Complete' : 'Ingestion Failed'}</h3>
          </div>
          {result.ok ? (
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: 'Total Rows', value: result.data.total_rows, color: 'text-txt-primary' },
                { label: 'Parsed', value: result.data.parsed_rows, color: 'text-emerald-600' },
                { label: 'Failed', value: result.data.failed_rows, color: 'text-red-500' },
                { label: 'Suspicious', value: result.data.suspicious_rows, color: 'text-amber-500' },
              ].map((m) => (
                <div key={m.label} className="px-4 py-3 rounded-xl bg-surface-secondary border border-surface-border-light">
                  <p className="text-2xs text-txt-faint mb-0.5">{m.label}</p>
                  <p className={`text-xl font-extrabold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-red-500">{result.data}</p>}
        </div>
      )}
    </div>
  );
}

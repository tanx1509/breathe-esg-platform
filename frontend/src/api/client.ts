import axios from 'axios';
import type {
  AuthTokens,
  PaginatedResponse,
  QueueRecord,
  RecordDetail,
  IngestionJob,
  IngestionStats,
} from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Token management ─────────────────────────────────────────────────
export function getTokens(): AuthTokens | null {
  const access = localStorage.getItem('access_token');
  const refresh = localStorage.getItem('refresh_token');
  if (access && refresh) return { access, refresh };
  return null;
}

export function setTokens(tokens: AuthTokens) {
  localStorage.setItem('access_token', tokens.access);
  localStorage.setItem('refresh_token', tokens.refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function isAuthenticated(): boolean {
  const tokens = getTokens();
  if (!tokens) return false;
  try {
    const payload = JSON.parse(atob(tokens.access.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getDecodedToken() {
  const tokens = getTokens();
  if (!tokens) return null;
  try {
    return JSON.parse(atob(tokens.access.split('.')[1]));
  } catch {
    return null;
  }
}

// ─── Interceptors ─────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const tokens = getTokens();
  if (tokens) {
    config.headers.Authorization = `Bearer ${tokens.access}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const tokens = getTokens();
      if (tokens?.refresh) {
        try {
          const res = await axios.post(`${API_BASE}/auth/token/refresh/`, {
            refresh: tokens.refresh,
          });
          setTokens({ access: res.data.access, refresh: tokens.refresh });
          original.headers.Authorization = `Bearer ${res.data.access}`;
          return api(original);
        } catch {
          clearTokens();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────────
export async function login(username: string, password: string): Promise<AuthTokens> {
  const res = await api.post('/auth/token/', { username, password });
  setTokens(res.data);
  return res.data;
}

export function logout() {
  clearTokens();
  window.location.href = '/login';
}

// ─── Review Queue ─────────────────────────────────────────────────────
export async function fetchReviewQueue(
  params: Record<string, string> = {}
): Promise<PaginatedResponse<QueueRecord>> {
  const res = await api.get('/review/queue/', { params });
  return res.data;
}

// ─── Record Detail ────────────────────────────────────────────────────
export async function fetchRecordDetail(id: string): Promise<RecordDetail> {
  const res = await api.get(`/review/record/${id}/`);
  return res.data;
}

// ─── Review Actions ───────────────────────────────────────────────────
export async function approveRecord(id: string, notes: string = '') {
  const res = await api.post(`/review/record/${id}/approve/`, { notes });
  return res.data;
}

export async function rejectRecord(id: string, notes: string) {
  const res = await api.post(`/review/record/${id}/reject/`, { notes });
  return res.data;
}

export async function editRecord(
  id: string,
  fields_edited: Record<string, { value: unknown; reason: string }>,
  notes: string
) {
  const res = await api.post(`/review/record/${id}/edit/`, { fields_edited, notes });
  return res.data;
}

export async function resolveFlag(flagId: string, resolution_note: string) {
  const res = await api.post(`/review/flag/${flagId}/resolve/`, {
    resolution_status: 'ANALYST_RESOLVED',
    resolution_note,
  });
  return res.data;
}

// ─── Ingestion ────────────────────────────────────────────────────────
export async function fetchIngestionStats(): Promise<IngestionStats[]> {
  const res = await api.get('/ingest/stats/');
  return res.data;
}

export async function fetchJobs(
  params: Record<string, string> = {}
): Promise<PaginatedResponse<IngestionJob>> {
  const res = await api.get('/ingest/jobs/', { params });
  return res.data;
}

export async function uploadFile(file: File, sourceType: string): Promise<IngestionJob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_type', sourceType);
  const res = await api.post('/ingest/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export default api;

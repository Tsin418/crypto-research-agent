import type { DashboardData, Direction, SnapshotEnvelope } from './types';

export function getLayerData<T extends Record<string, unknown>>(dashboardData: DashboardData | undefined, layer: string): T {
  const snapshot = dashboardData?.snapshots?.[layer] as SnapshotEnvelope<T> | undefined;
  const payload = snapshot?.data;

  if (payload && typeof payload === 'object' && 'data' in payload) {
    return ((payload as { data?: T }).data || {}) as T;
  }

  return (payload || {}) as T;
}

export function formatLabel(value: string | null | undefined) {
  if (!value) {
    return 'n/a';
  }
  return value.replaceAll('_', ' ');
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return 'n/a';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatNumber(value: number | string | null | undefined, options?: Intl.NumberFormatOptions) {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return new Intl.NumberFormat(undefined, options).format(numeric);
}

export function formatPercent(value: number | string | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(maximumFractionDigits)}%`;
}

export function formatCurrency(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: numeric >= 1000 ? 0 : 2,
  }).format(numeric);
}

export function badgeClasses(value: Direction | null | undefined) {
  const normalized = String(value || 'neutral').toLowerCase();

  if (normalized.includes('bull') || normalized === 'low') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }

  if (normalized.includes('bear') || normalized.includes('high')) {
    return 'border-[#f2c5b4] bg-[#fff4ef] text-[#b64a22]';
  }

  if (normalized.includes('medium')) {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }

  return 'border-[#d9d9d5] bg-[#f5f5f2] text-[#5d646a]';
}

export function clampPercent(value: number | undefined, max = 12) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(100, Math.max(0, ((value || 0) / max) * 100));
}

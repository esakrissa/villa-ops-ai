/**
 * Parse a timestamp from the API.
 *
 * The backend stores naive UTC datetimes and serializes them without a
 * timezone suffix (e.g. "2026-11-03T15:50:27"). `new Date()` would read
 * those as local time, so treat suffix-less timestamps as UTC.
 */
export function parseApiDate(value: string): Date {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatRelativeTime(value: string): string {
  const date = parseApiDate(value);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

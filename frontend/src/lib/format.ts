const pad = (n: number) => String(n).padStart(2, "0");

/** Local time as `YYYY-MM-DD HH:MM:SS`: sortable, fixed-width, and unambiguous in a log. */
export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

/** "just now", "5m ago", "3h ago", "2d ago", falling back to the date for anything older than a week. */
export function formatRelative(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 7 * 86400) return `${Math.floor(seconds / 86400)}d ago`;
  return formatTimestamp(iso).slice(0, 10);
}

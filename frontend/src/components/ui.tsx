import type { ContractStatus } from "../types";

export function StatusBadge({ status }: { status: ContractStatus }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

export function RoleBadge({ role }: { role: "owner" | "viewer" }) {
  if (role === "owner") return null;
  return <span className="badge viewer">shared</span>;
}

export function DaysLeft(expiry: string | null): number | null {
  if (!expiry) return null;
  const diff = new Date(expiry).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function ExpiryLabel({ expiry }: { expiry: string | null }) {
  if (!expiry) return <span className="muted">—</span>;
  const days = DaysLeft(expiry);
  if (days === null) return <span>{expiry}</span>;
  if (days < 0) return <span className="badge expired">expired {Math.abs(days)}d ago</span>;
  if (days <= 30) return <span className="days-urgent">{expiry} · {days}d</span>;
  if (days <= 90) return <span className="days-warn">{expiry} · {days}d</span>;
  return <span>{expiry}</span>;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function valueLabel(value: string | null, currency: string | null): string {
  if (value === null) return "";
  return `${currency ?? ""} ${value}`.trim();
}

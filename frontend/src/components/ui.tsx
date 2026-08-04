import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import type { ContractStatus } from "../types";

export function categoryLabel(t: TFunction, category: string | null): string {
  if (!category) return "—";
  return t(`categories.${category}`, { defaultValue: category });
}

export function groupLabel(t: TFunction, group: string): string {
  return t(`categoryGroups.${group}`, { defaultValue: group });
}

export function CategoryLabel({ category }: { category: string | null }) {
  const { t } = useTranslation();
  return <>{categoryLabel(t, category)}</>;
}

export function StatusBadge({ status }: { status: ContractStatus }) {
  const { t } = useTranslation();
  return <span className={`badge ${status}`}>{t(`status.${status}`)}</span>;
}

export function RoleBadge({ role }: { role: "owner" | "viewer" }) {
  const { t } = useTranslation();
  if (role === "owner") return null;
  return <span className="badge viewer">{t("role.shared")}</span>;
}

export function DaysLeft(expiry: string | null): number | null {
  if (!expiry) return null;
  const diff = new Date(expiry).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function formatDate(date: string | null, locale: string): string | null {
  if (!date) return null;
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(y, m - 1, d).toLocaleDateString(locale, { year: "numeric", month: "2-digit", day: "2-digit" });
}

export function ExpiryLabel({ expiry }: { expiry: string | null }) {
  const { t, i18n } = useTranslation();
  if (!expiry) return <span className="muted">—</span>;
  const days = DaysLeft(expiry);
  const label = formatDate(expiry, i18n.language) ?? expiry;
  if (days === null) return <span>{label}</span>;
  if (days < 0) return <span className="badge expired">{t("expiry.expiredAgo", { count: Math.abs(days) })}</span>;
  if (days <= 30) return <span className="days-urgent">{label} · {t("expiry.daysShort", { count: days })}</span>;
  if (days <= 90) return <span className="days-warn">{label} · {t("expiry.daysShort", { count: days })}</span>;
  return <span>{label}</span>;
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

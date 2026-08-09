import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Dashboard } from "../types";
import { DaysLeft, ExpiryLabel, RoleBadge, categoryLabel } from "../components/ui";

export function Dashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="empty">{t("app.loading")}</div>;

  const total = Object.values(data.status_counts).reduce((a, b) => a + b, 0);

  return (
    <>
      <div className="page-header">
        <h1>{t("dashboard.title")}</h1>
        <Link className="btn" to="/contracts/new">
          {t("dashboard.newContract")}
        </Link>
      </div>

      <div className="grid" style={{ marginBottom: 20 }}>
        <div className="stat">
          <div className="num">{total}</div>
          <div className="lbl">{t("dashboard.contracts")}</div>
        </div>
        <div className="stat">
          <div className="num">{data.expiring_soon.length}</div>
          <div className="lbl">{t("dashboard.expiring90")}</div>
        </div>
        <div className="stat">
          <div className="num">{data.status_counts["active"] ?? 0}</div>
          <div className="lbl">{t("dashboard.active")}</div>
        </div>
        <div className="stat">
          <div className="num">{data.status_counts["expired"] ?? 0}</div>
          <div className="lbl">{t("dashboard.expired")}</div>
        </div>
        <div className="stat">
          <div className="num">
            {(data.status_counts["expired"] ?? 0) + (data.status_counts["terminated"] ?? 0)}
          </div>
          <div className="lbl">{t("dashboard.archived")}</div>
        </div>
      </div>

      <div className="card">
        <h2>{t("dashboard.expiringSoon")}</h2>
        {data.expiring_soon.length === 0 ? (
          <div className="empty">{t("dashboard.nothingExpiring")}</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("common.status")}</th>
                <th>{t("common.counterparty")}</th>
                <th>{t("common.expiry")}</th>
                <th>{t("common.days")}</th>
              </tr>
            </thead>
            <tbody>
              {data.expiring_soon.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/contracts/${c.id}`}>{c.title}</Link> <RoleBadge role={c.role} />
                  </td>
                  <td>
                    <span className={`badge ${c.status}`}>{c.status}</span>
                  </td>
                  <td>{c.counterparty?.name ?? "—"}</td>
                  <td>
                    <ExpiryLabel expiry={c.expiry_date} />
                  </td>
                  <td>{DaysLeft(c.expiry_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="grid">
        <div className="card">
          <h2>{t("dashboard.byStatus")}</h2>
          {Object.entries(data.status_counts).map(([status, count]) => (
            <div key={status} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <span className="badge">{t(`status.${status}`)}</span>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
        <div className="card">
          <h2>{t("dashboard.byCategory")}</h2>
          {data.category_counts.length === 0 ? (
            <div className="muted">{t("dashboard.noCategories")}</div>
          ) : (
            data.category_counts.map((c) => (
              <div key={c.key} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                <span>{categoryLabel(t, c.key)}</span>
                <strong>{c.count}</strong>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

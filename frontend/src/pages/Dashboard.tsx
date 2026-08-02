import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Dashboard } from "../types";
import { DaysLeft, ExpiryLabel, RoleBadge } from "../components/ui";

export function Dashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="empty">Loading…</div>;

  const total = Object.values(data.status_counts).reduce((a, b) => a + b, 0);

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <Link className="btn" to="/contracts/new">
          + New contract
        </Link>
      </div>

      <div className="grid" style={{ marginBottom: 20 }}>
        <div className="stat">
          <div className="num">{total}</div>
          <div className="lbl">Contracts</div>
        </div>
        <div className="stat">
          <div className="num">{data.expiring_soon.length}</div>
          <div className="lbl">Expiring in 90 days</div>
        </div>
        <div className="stat">
          <div className="num">{data.status_counts["active"] ?? 0}</div>
          <div className="lbl">Active</div>
        </div>
        <div className="stat">
          <div className="num">{data.status_counts["expired"] ?? 0}</div>
          <div className="lbl">Expired</div>
        </div>
      </div>

      <div className="card">
        <h2>Expiring soon</h2>
        {data.expiring_soon.length === 0 ? (
          <div className="empty">Nothing expiring in the next 90 days.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Counterparty</th>
                <th>Expiry</th>
                <th>Days</th>
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
          <h2>By status</h2>
          {Object.entries(data.status_counts).map(([status, count]) => (
            <div key={status} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <span className="badge">{status}</span>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
        <div className="card">
          <h2>By category</h2>
          {data.category_counts.length === 0 ? (
            <div className="muted">No categories yet.</div>
          ) : (
            data.category_counts.map((c) => (
              <div key={c.name} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                <span>{c.name}</span>
                <strong>{c.count}</strong>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

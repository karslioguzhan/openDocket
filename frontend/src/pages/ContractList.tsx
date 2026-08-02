import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Contract, ContractStatus } from "../types";
import { ExpiryLabel, RoleBadge, valueLabel } from "../components/ui";

const STATUSES: Array<ContractStatus | ""> = ["", "draft", "active", "expired", "terminated"];

export function ContractList() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | ContractStatus>("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (debounced) params.set("search", debounced);
      if (status) params.set("status", status);
      const rows = await api<Contract[]>(`/contracts?${params.toString()}`);
      setContracts(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [debounced, status]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="page-header">
        <h1>Contracts</h1>
        <Link className="btn" to="/contracts/new">
          + New contract
        </Link>
      </div>

      <div className="card" style={{ display: "flex", gap: 12 }}>
        <input
          placeholder="Search title, notes, counterparty, tags…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1 }}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value as ContractStatus)} style={{ width: 180 }}>
          {STATUSES.map((s) => (
            <option key={s || "all"} value={s}>
              {s === "" ? "All statuses" : s}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error">{error}</div>}

      {contracts.length === 0 ? (
        <div className="card empty">No contracts found.</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Status</th>
                <th>Counterparty</th>
                <th>Category</th>
                <th>Expiry</th>
                <th>Value</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/contracts/${c.id}`}>{c.title}</Link> <RoleBadge role={c.role} />
                  </td>
                  <td>
                    <span className={`badge ${c.status}`}>{c.status}</span>
                  </td>
                  <td>{c.counterparty?.name ?? "—"}</td>
                  <td>{c.category?.name ?? "—"}</td>
                  <td>
                    <ExpiryLabel expiry={c.expiry_date} />
                  </td>
                  <td>{valueLabel(c.value, c.currency) || "—"}</td>
                  <td>
                    <div className="tags">
                      {c.tags.map((t) => (
                        <span key={t} className="tag">
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

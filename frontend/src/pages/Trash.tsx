import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Contract } from "../types";

export function Trash() {
  const [rows, setRows] = useState<Contract[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api<Contract[]>("/contracts?trashed=true"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const restore = async (id: string) => {
    await api<Contract>(`/contracts/${id}/restore`, { method: "POST" });
    await load();
  };

  return (
    <>
      <div className="page-header">
        <h1>Trash</h1>
      </div>
      <div className="card muted">
        Contracts in trash are purged automatically after 30 days.
      </div>
      {error && <div className="error">{error}</div>}
      {rows.length === 0 ? (
        <div className="card empty">Trash is empty.</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Deleted</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/contracts/${c.id}`}>{c.title}</Link>
                  </td>
                  <td>{c.deleted_at ? new Date(c.deleted_at).toLocaleDateString() : "—"}</td>
                  <td>
                    <button className="secondary" onClick={() => restore(c.id)}>
                      Restore
                    </button>
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

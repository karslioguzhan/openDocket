import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Counterparty } from "../types";

export function Counterparties() {
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api<Counterparty[]>("/counterparties"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;
    setError(null);
    try {
      await api<Counterparty>("/counterparties", {
        method: "POST",
        body: JSON.stringify({ name, email: email || null, phone: phone || null }),
      });
      setName("");
      setEmail("");
      setPhone("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this counterparty? It cannot be deleted while referenced by contracts.")) return;
    try {
      await api<void>(`/counterparties/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Counterparties</h1>
      </div>
      {error && <div className="error">{error}</div>}

      <form className="card" onSubmit={add} style={{ display: "flex", gap: 10 }}>
        <input placeholder="Name *" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <button type="submit">Add</button>
      </form>

      {rows.length === 0 ? (
        <div className="card empty">No counterparties yet.</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.email ?? "—"}</td>
                  <td>{c.phone ?? "—"}</td>
                  <td>
                    <button className="danger" style={{ padding: "4px 10px" }} onClick={() => remove(c.id)}>
                      Delete
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

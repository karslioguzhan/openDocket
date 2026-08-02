import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { User } from "../types";

export function Admin() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await api<User[]>("/users"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await api<User>("/users", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setEmail("");
      setPassword("");
      setNotice(`Created account for ${email}. Share the password with them.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  };

  const setActive = async (u: User, is_active: boolean) => {
    try {
      await api<User>(`/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  };

  const resetPassword = async (u: User) => {
    const pw = prompt(`New password for ${u.email}:`);
    if (!pw) return;
    try {
      await api<User>(`/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ password: pw }),
      });
      setNotice(`Password reset for ${u.email}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  };

  const removeUser = async (u: User) => {
    if (!confirm(`Delete account ${u.email}? Their contracts are deleted too.`)) return;
    try {
      await api<void>(`/users/${u.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>Admin — user management</h1>
      </div>
      {error && <div className="error">{error}</div>}
      {notice && <div className="card" style={{ background: "#e2f5ea", borderColor: "#b5e0c3" }}>{notice}</div>}

      <form className="card" onSubmit={createUser} style={{ display: "flex", gap: 10 }}>
        <input type="email" placeholder="new@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder="Initial password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <button type="submit">Create account</button>
      </form>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table>
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Active</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.is_superuser ? <span className="badge">admin</span> : <span className="badge">user</span>}</td>
                <td>{u.is_active ? "yes" : "no"}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => resetPassword(u)}>
                    Reset password
                  </button>
                  {u.is_active ? (
                    <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => setActive(u, false)}>
                      Disable
                    </button>
                  ) : (
                    <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => setActive(u, true)}>
                      Enable
                    </button>
                  )}
                  {!u.is_superuser && (
                    <button className="danger" style={{ padding: "4px 10px" }} onClick={() => removeUser(u)}>
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

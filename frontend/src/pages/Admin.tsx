import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { User } from "../types";

export function Admin() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await api<User[]>("/users"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("admin.loadFailed"));
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
      setNotice(t("admin.created", { email }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("admin.createFailed"));
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
      setError(err instanceof Error ? err.message : t("admin.updateFailed"));
    }
  };

  const resetPassword = async (u: User) => {
    const pw = prompt(t("admin.newPasswordPrompt", { email: u.email }));
    if (!pw) return;
    try {
      await api<User>(`/users/${u.id}`, {
        method: "PATCH",
        body: JSON.stringify({ password: pw }),
      });
      setNotice(t("admin.passwordReset", { email: u.email }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("admin.resetFailed"));
    }
  };

  const removeUser = async (u: User) => {
    if (!confirm(t("admin.deleteConfirm", { email: u.email }))) return;
    try {
      await api<void>(`/users/${u.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("admin.deleteFailed"));
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("admin.title")}</h1>
      </div>
      {error && <div className="error">{error}</div>}
      {notice && <div className="card notice success">{notice}</div>}

      <form className="card" onSubmit={createUser} style={{ display: "flex", gap: 10 }}>
        <input type="email" placeholder={t("admin.emailPlaceholder")} value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder={t("admin.initialPassword")}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <button type="submit">{t("admin.createAccount")}</button>
      </form>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table>
          <thead>
            <tr>
              <th>{t("common.email")}</th>
              <th>{t("admin.role")}</th>
              <th>{t("admin.active")}</th>
              <th>{t("admin.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.is_superuser ? <span className="badge">{t("nav.admin")}</span> : <span className="badge">user</span>}</td>
                <td>{u.is_active ? t("admin.yes") : t("admin.no")}</td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => resetPassword(u)}>
                    {t("admin.resetPassword")}
                  </button>
                  {u.is_active ? (
                    <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => setActive(u, false)}>
                      {t("admin.disable")}
                    </button>
                  ) : (
                    <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => setActive(u, true)}>
                      {t("admin.enable")}
                    </button>
                  )}
                  {!u.is_superuser && (
                    <button className="danger" style={{ padding: "4px 10px" }} onClick={() => removeUser(u)}>
                      {t("admin.delete")}
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

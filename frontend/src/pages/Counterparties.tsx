import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Counterparty } from "../types";

export function Counterparties() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api<Counterparty[]>("/counterparties"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("counterparties.loadFailed"));
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
      setError(err instanceof Error ? err.message : t("counterparties.saveFailed"));
    }
  };

  const remove = async (id: string) => {
    if (!confirm(t("counterparties.deleteConfirm"))) return;
    try {
      await api<void>(`/counterparties/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("counterparties.deleteFailed"));
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("counterparties.title")}</h1>
      </div>
      {error && <div className="error">{error}</div>}

      <form className="card" onSubmit={add} style={{ display: "flex", gap: 10 }}>
        <input placeholder={t("counterparties.nameRequired")} value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder={t("counterparties.email")} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder={t("counterparties.phone")} value={phone} onChange={(e) => setPhone(e.target.value)} />
        <button type="submit">{t("counterparties.add")}</button>
      </form>

      {rows.length === 0 ? (
        <div className="card empty">{t("counterparties.noCounterparties")}</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>{t("common.name")}</th>
                <th>{t("common.email")}</th>
                <th>{t("common.phone")}</th>
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
                      {t("common.delete")}
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

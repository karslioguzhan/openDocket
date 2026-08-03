import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Contract } from "../types";

export function Trash() {
  const { t, i18n } = useTranslation();
  const [rows, setRows] = useState<Contract[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api<Contract[]>("/contracts?trashed=true"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("trash.loadFailed"));
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
        <h1>{t("trash.title")}</h1>
      </div>
      <div className="card muted">
        {t("trash.note")}
      </div>
      {error && <div className="error">{error}</div>}
      {rows.length === 0 ? (
        <div className="card empty">{t("trash.empty")}</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("trash.deleted")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/contracts/${c.id}`}>{c.title}</Link>
                  </td>
                  <td>{c.deleted_at ? new Date(c.deleted_at).toLocaleDateString(i18n.language) : "—"}</td>
                  <td>
                    <button className="secondary" onClick={() => restore(c.id)}>
                      {t("trash.restore")}
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

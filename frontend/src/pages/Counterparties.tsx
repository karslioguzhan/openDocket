import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Counterparty } from "../types";

interface EditDraft {
  name: string;
  type: string;
  email: string;
  phone: string;
}

interface ModalDraft extends EditDraft {
  notes: string;
}

export function Counterparties() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("company");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({ name: "", type: "company", email: "", phone: "" });
  const [modal, setModal] = useState<Counterparty | null>(null);
  const [modalDraft, setModalDraft] = useState<ModalDraft>({ name: "", type: "company", email: "", phone: "", notes: "" });

  const load = useCallback(async () => {
    try {
      setRows(await api<Counterparty[]>("/counterparties"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("counterparties.loadFailed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name) return;
    setError(null);
    setBusy(true);
    try {
      await api<Counterparty>("/counterparties", {
        method: "POST",
        body: JSON.stringify({
          name,
          type,
          email: email || null,
          phone: phone || null,
          notes: notes || null,
        }),
      });
      setName("");
      setType("company");
      setEmail("");
      setPhone("");
      setNotes("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("counterparties.saveFailed"));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (c: Counterparty) => {
    setEditingId(c.id);
    setEditDraft({ name: c.name, type: c.type, email: c.email ?? "", phone: c.phone ?? "" });
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async (id: string) => {
    setError(null);
    setBusy(true);
    try {
      await api<Counterparty>(`/counterparties/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editDraft.name,
          type: editDraft.type,
          email: editDraft.email || null,
          phone: editDraft.phone || null,
        }),
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("counterparties.updateFailed"));
    } finally {
      setBusy(false);
    }
  };

  const openModal = (c: Counterparty) => {
    setModal(c);
    setModalDraft({
      name: c.name,
      type: c.type,
      email: c.email ?? "",
      phone: c.phone ?? "",
      notes: c.notes ?? "",
    });
  };

  const closeModal = () => setModal(null);

  const saveModal = async (id: string) => {
    setError(null);
    setBusy(true);
    try {
      await api<Counterparty>(`/counterparties/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: modalDraft.name,
          type: modalDraft.type,
          email: modalDraft.email || null,
          phone: modalDraft.phone || null,
          notes: modalDraft.notes || null,
        }),
      });
      setModal(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("counterparties.updateFailed"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!confirm(t("counterparties.deleteConfirm"))) return;
    setError(null);
    setBusy(true);
    try {
      await api<void>(`/counterparties/${id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("counterparties.deleteFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("counterparties.title")}</h1>
      </div>
      {error && <div className="error">{error}</div>}

      <form className="card" onSubmit={add} style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input placeholder={t("counterparties.nameRequired")} value={name} onChange={(e) => setName(e.target.value)} required />
        <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: 170 }}>
          <option value="company">{t("counterpartyType.company")}</option>
          <option value="person">{t("counterpartyType.person")}</option>
        </select>
        <input placeholder={t("counterparties.email")} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input placeholder={t("counterparties.phone")} value={phone} onChange={(e) => setPhone(e.target.value)} />
        <input placeholder={t("counterparties.notes")} value={notes} onChange={(e) => setNotes(e.target.value)} />
        <button type="submit" disabled={busy}>
          {t("counterparties.add")}
        </button>
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
              {rows.map((c) => {
                const editing = editingId === c.id;
                return (
                  <tr key={c.id}>
                    {editing ? (
                      <>
                        <td>
                          <input
                            value={editDraft.name}
                            onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                            autoFocus
                          />
                          <select
                            value={editDraft.type}
                            onChange={(e) => setEditDraft((d) => ({ ...d, type: e.target.value }))}
                            style={{ width: 170, marginTop: 6 }}
                          >
                            <option value="company">{t("counterpartyType.company")}</option>
                            <option value="person">{t("counterpartyType.person")}</option>
                          </select>
                        </td>
                        <td>
                          <input
                            type="email"
                            value={editDraft.email}
                            onChange={(e) => setEditDraft((d) => ({ ...d, email: e.target.value }))}
                          />
                        </td>
                        <td>
                          <input
                            value={editDraft.phone}
                            onChange={(e) => setEditDraft((d) => ({ ...d, phone: e.target.value }))}
                          />
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                            <button disabled={busy} onClick={() => saveEdit(c.id)}>
                              {t("counterparties.save")}
                            </button>
                            <button className="secondary" onClick={cancelEdit}>
                              {t("common.cancel")}
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td>
                          {c.name}{" "}
                          <span className={`badge cp-type cp-${c.type}`}>{t(`counterpartyType.${c.type}`)}</span>
                        </td>
                        <td>{c.email ?? "—"}</td>
                        <td>{c.phone ?? "—"}</td>
                        <td>
                          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                            <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => startEdit(c)}>
                              {t("counterparties.edit")}
                            </button>
                            <button className="secondary" style={{ padding: "4px 10px" }} onClick={() => openModal(c)}>
                              {t("counterparties.details")}
                            </button>
                            <button className="danger" style={{ padding: "4px 10px" }} onClick={() => remove(c.id)}>
                              {t("common.delete")}
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{t("counterparties.editTitle")}</h2>
            <label>{t("common.name")}</label>
            <input
              value={modalDraft.name}
              onChange={(e) => setModalDraft((d) => ({ ...d, name: e.target.value }))}
            />
            <label>{t("counterparties.type")}</label>
            <select
              value={modalDraft.type}
              onChange={(e) => setModalDraft((d) => ({ ...d, type: e.target.value }))}
            >
              <option value="company">{t("counterpartyType.company")}</option>
              <option value="person">{t("counterpartyType.person")}</option>
            </select>
            <label>{t("common.email")}</label>
            <input
              type="email"
              value={modalDraft.email}
              onChange={(e) => setModalDraft((d) => ({ ...d, email: e.target.value }))}
            />
            <label>{t("common.phone")}</label>
            <input
              value={modalDraft.phone}
              onChange={(e) => setModalDraft((d) => ({ ...d, phone: e.target.value }))}
            />
            <label>{t("common.notes")}</label>
            <textarea
              rows={3}
              value={modalDraft.notes}
              onChange={(e) => setModalDraft((d) => ({ ...d, notes: e.target.value }))}
            />
            <div style={{ marginTop: 14, display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button disabled={busy} onClick={() => saveModal(modal.id)}>
                {t("counterparties.save")}
              </button>
              <button className="secondary" onClick={closeModal}>
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

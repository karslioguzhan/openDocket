import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type { Category, Contract, ContractPayload, ContractStatus, Counterparty } from "../types";

const STATUSES: ContractStatus[] = ["draft", "active", "expired", "terminated"];

interface FormState {
  title: string;
  status: ContractStatus;
  counterparty_id: string;
  category_id: string;
  tags: string;
  effective_date: string;
  expiry_date: string;
  notice_days: string;
  notes: string;
  value: string;
  currency: string;
}

const empty: FormState = {
  title: "",
  status: "draft",
  counterparty_id: "",
  category_id: "",
  tags: "",
  effective_date: "",
  expiry_date: "",
  notice_days: "",
  notes: "",
  value: "",
  currency: "",
};

export function ContractForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const editing = Boolean(id);

  const [form, setForm] = useState<FormState>(empty);
  const [counterparties, setCounterparties] = useState<Counterparty[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api<Counterparty[]>("/counterparties").then(setCounterparties);
    void api<Category[]>("/meta/categories").then(setCategories);
  }, []);

  useEffect(() => {
    if (!id) return;
    api<Contract>(`/contracts/${id}`)
      .then((c) =>
        setForm({
          title: c.title,
          status: c.status,
          counterparty_id: c.counterparty?.id ?? "",
          category_id: c.category?.id ?? "",
          tags: c.tags.join(", "),
          effective_date: c.effective_date ?? "",
          expiry_date: c.expiry_date ?? "",
          notice_days: c.notice_days?.toString() ?? "",
          notes: c.notes ?? "",
          value: c.value ?? "",
          currency: c.currency ?? "",
        }),
      )
      .catch((e) => setError(e.message));
  }, [id]);

  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const payload: ContractPayload = {
      title: form.title,
      status: form.status,
      counterparty_id: form.counterparty_id || null,
      category_id: form.category_id || null,
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      effective_date: form.effective_date || null,
      expiry_date: form.expiry_date || null,
      notice_days: form.notice_days === "" ? null : Number(form.notice_days),
      notes: form.notes || null,
      value: form.value === "" ? null : form.value,
      currency: form.currency || null,
    };
    try {
      const saved = editing
        ? await api<Contract>(`/contracts/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await api<Contract>("/contracts", { method: "POST", body: JSON.stringify(payload) });
      navigate(`/contracts/${saved.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{editing ? "Edit contract" : "New contract"}</h1>
      </div>
      {error && <div className="error">{error}</div>}
      <form className="card" onSubmit={submit}>
        <label>Title *</label>
        <input value={form.title} onChange={set("title")} required />

        <div className="form-grid">
          <div>
            <label>Status</label>
            <select value={form.status} onChange={set("status")}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Counterparty</label>
            <select value={form.counterparty_id} onChange={set("counterparty_id")}>
              <option value="">— None —</option>
              {counterparties.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Category</label>
            <select value={form.category_id} onChange={set("category_id")}>
              <option value="">— None —</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Tags (comma separated)</label>
            <input value={form.tags} onChange={set("tags")} placeholder="home, monthly" />
          </div>
          <div>
            <label>Effective date</label>
            <input type="date" value={form.effective_date} onChange={set("effective_date")} />
          </div>
          <div>
            <label>Expiry / renewal date</label>
            <input type="date" value={form.expiry_date} onChange={set("expiry_date")} />
          </div>
          <div>
            <label>Notice period (days)</label>
            <input type="number" min={0} value={form.notice_days} onChange={set("notice_days")} />
          </div>
          <div>
            <label>Value</label>
            <input type="number" step="0.01" min={0} value={form.value} onChange={set("value")} />
          </div>
          <div>
            <label>Currency (ISO 4217)</label>
            <input value={form.currency} onChange={set("currency")} placeholder="USD" maxLength={3} />
          </div>
          <div className="full">
            <label>Notes</label>
            <textarea rows={4} value={form.notes} onChange={set("notes")} />
          </div>
        </div>

        <div style={{ marginTop: 18, display: "flex", gap: 10 }}>
          <button type="submit" disabled={busy || !form.title}>
            {editing ? "Save changes" : "Create contract"}
          </button>
          <button type="button" className="secondary" onClick={() => navigate(-1)}>
            Cancel
          </button>
        </div>
      </form>
    </>
  );
}

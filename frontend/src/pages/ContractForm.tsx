import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { categoryLabel, formatBytes, groupLabel } from "../components/ui";
import type {
  CategoryMeta,
  Contract,
  ContractFile,
  ContractPayload,
  ContractStatus,
  Counterparty,
  ExtractionResult,
} from "../types";

const STATUSES: ContractStatus[] = ["draft", "active", "expired", "terminated"];

const CURRENCIES = ["EUR", "USD", "TRY"];

const SCAN_ACCEPT = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt";

interface FormState {
  title: string;
  status: ContractStatus;
  counterparty_id: string;
  category: string;
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
  category: "",
  tags: "",
  effective_date: "",
  expiry_date: "",
  notice_days: "",
  notes: "",
  value: "",
  currency: "EUR",
};

type Mode = "choose" | "manual" | "scan";

export function ContractForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const editing = Boolean(id);

  const [mode, setMode] = useState<Mode>(editing ? "manual" : "choose");
  const [form, setForm] = useState<FormState>(empty);
  const [counterparties, setCounterparties] = useState<Counterparty[]>([]);
  const [categories, setCategories] = useState<CategoryMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scanFiles, setScanFiles] = useState<File[]>([]);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [extracting, setExtracting] = useState(false);

  useEffect(() => {
    void api<Counterparty[]>("/counterparties").then(setCounterparties);
    void api<CategoryMeta[]>("/meta/categories").then(setCategories);
  }, []);

  const categoryGroups = categories.reduce<Record<string, CategoryMeta[]>>((acc, c) => {
    (acc[c.group] ??= []).push(c);
    return acc;
  }, {});

  useEffect(() => {
    if (!id) return;
    api<Contract>(`/contracts/${id}`)
      .then((c) =>
        setForm({
          title: c.title,
          status: c.status,
          counterparty_id: c.counterparty?.id ?? "",
          category: c.category ?? "",
          tags: c.tags.join(", "),
          effective_date: c.effective_date ?? "",
          expiry_date: c.expiry_date ?? "",
          notice_days: c.notice_days?.toString() ?? "",
          notes: c.notes ?? "",
          value: c.value ?? "",
          currency: CURRENCIES.includes(c.currency ?? "") ? (c.currency as string) : "EUR",
        }),
      )
      .catch((e) => setError(e.message));
  }, [id]);

  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const goChoose = () => {
    setMode("choose");
    setScanFiles([]);
    setExtraction(null);
    setForm(empty);
    setError(null);
  };

  const matchCounterparty = (name: string | null): string => {
    if (!name) return "";
    const n = name.trim().toLowerCase();
    const found = counterparties.find(
      (c) => c.name.toLowerCase().includes(n) || n.includes(c.name.toLowerCase()),
    );
    return found?.id ?? "";
  };

  const onScanFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    setScanFiles((prev) => [...prev, ...files]);
    e.target.value = "";
  };

  const extract = async () => {
    if (scanFiles.length === 0) return;
    setExtracting(true);
    setError(null);
    const body = new FormData();
    for (const f of scanFiles) body.append("files", f);
    try {
      const res = await api<ExtractionResult>("/contracts/extract", { method: "POST", body });
      setExtraction(res);
      setForm({
        ...empty,
        title: res.title ?? "",
        counterparty_id: matchCounterparty(res.counterparty_name),
        effective_date: res.effective_date ?? "",
        expiry_date: res.expiry_date ?? "",
        notice_days: res.notice_days?.toString() ?? "",
        value: res.value ?? "",
        currency: CURRENCIES.includes(res.currency ?? "") ? (res.currency as string) : "EUR",
      });
      setMode("manual");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("contractForm.extractFailed"));
    } finally {
      setExtracting(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const payload: ContractPayload = {
      title: form.title,
      status: form.status,
      counterparty_id: form.counterparty_id || null,
      category: form.category || null,
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      effective_date: form.effective_date || null,
      expiry_date: form.expiry_date || null,
      notice_days: form.notice_days === "" ? null : Number(form.notice_days),
      notes: form.notes || null,
      value: form.value === "" ? null : form.value,
      currency: form.currency,
    };
    try {
      const saved = editing
        ? await api<Contract>(`/contracts/${id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await api<Contract>("/contracts", { method: "POST", body: JSON.stringify(payload) });
      if (!editing && scanFiles.length > 0) {
        for (const file of scanFiles) {
          const body = new FormData();
          body.append("file", file);
          await api<ContractFile>(`/contracts/${saved.id}/files`, { method: "POST", body });
        }
      }
      navigate(`/contracts/${saved.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("contractForm.saveFailed"));
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{editing ? t("contractForm.editTitle") : t("contractForm.newTitle")}</h1>
      </div>
      {error && <div className="error">{error}</div>}

      {!editing && mode === "choose" && (
        <div className="mode-grid">
          <button type="button" className="card mode-card" onClick={() => setMode("manual")}>
            <h3>{t("contractForm.manualEntry")}</h3>
            <p className="muted">{t("contractForm.manualEntryHint")}</p>
          </button>
          <button type="button" className="card mode-card" onClick={() => setMode("scan")}>
            <h3>{t("contractForm.scanDocument")}</h3>
            <p className="muted">{t("contractForm.scanDocumentHint")}</p>
          </button>
        </div>
      )}

      {!editing && mode === "scan" && (
        <div className="card">
          <h2>{t("contractForm.scanStepTitle")}</h2>
          <p className="muted">{t("contractForm.scanStepHint")}</p>
          <label className="btn secondary" style={{ marginTop: 12, display: "inline-block", cursor: "pointer" }}>
            {t("contractForm.scanFiles", { count: scanFiles.length })}
            <input type="file" accept={SCAN_ACCEPT} multiple style={{ display: "none" }} onChange={onScanFiles} />
          </label>
          {scanFiles.length > 0 && (
            <ul className="file-list">
              {scanFiles.map((f, i) => (
                <li key={`${f.name}-${i}`}>
                  <span>
                    {f.name} <span className="muted">· {formatBytes(f.size)}</span>
                  </span>
                  <button
                    className="danger"
                    style={{ padding: "4px 10px" }}
                    onClick={() => setScanFiles(scanFiles.filter((_, j) => j !== i))}
                  >
                    {t("contractDetail.deleteFile")}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <button onClick={extract} disabled={extracting || scanFiles.length === 0}>
              {extracting ? t("contractForm.extracting") : t("contractForm.extract")}
            </button>
            <button type="button" className="secondary" onClick={goChoose}>
              {t("contractForm.backToChoice")}
            </button>
          </div>
        </div>
      )}

      {mode === "manual" && (
        <form className="card" onSubmit={submit}>
          {!editing && extraction && <div className="notice">{t("contractForm.reviewNotice")}</div>}
          {!editing && (
            <button type="button" className="secondary" style={{ marginBottom: 14 }} onClick={goChoose}>
              {t("contractForm.backToChoice")}
            </button>
          )}
          <label>{t("contractForm.titleRequired")}</label>
          <input value={form.title} onChange={set("title")} required />

          <div className="form-grid">
            <div>
              <label>{t("contractForm.status")}</label>
              <select value={form.status} onChange={set("status")}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`status.${s}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>{t("contractForm.counterparty")}</label>
              <select value={form.counterparty_id} onChange={set("counterparty_id")}>
                <option value="">{t("contractForm.none")}</option>
                {counterparties.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              {extraction?.counterparty_name && !form.counterparty_id && (
                <div className="muted" style={{ marginTop: 6 }}>
                  {t("contractForm.detectedCounterparty", { name: extraction.counterparty_name })}
                </div>
              )}
            </div>
            <div>
              <label>{t("contractForm.category")}</label>
              <select value={form.category} onChange={set("category")}>
                <option value="">{t("contractForm.none")}</option>
                {Object.entries(categoryGroups).map(([group, cats]) => (
                  <optgroup key={group} label={groupLabel(t, group)}>
                    {cats.map((c) => (
                      <option key={c.key} value={c.key}>
                        {categoryLabel(t, c.key)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            <div>
              <label>{t("contractForm.tagsLabel")}</label>
              <input value={form.tags} onChange={set("tags")} placeholder={t("contractForm.tagsPlaceholder")} />
            </div>
            <div>
              <label>{t("contractForm.effectiveDate")}</label>
              <input type="date" value={form.effective_date} onChange={set("effective_date")} />
            </div>
            <div>
              <label>{t("contractForm.expiryDate")}</label>
              <input type="date" value={form.expiry_date} onChange={set("expiry_date")} />
            </div>
            <div>
              <label>{t("contractForm.noticePeriod")}</label>
              <input type="number" min={0} value={form.notice_days} onChange={set("notice_days")} />
            </div>
            <div>
              <label>{t("contractForm.value")}</label>
              <input type="number" step="0.01" min={0} value={form.value} onChange={set("value")} />
            </div>
            <div>
              <label>{t("contractForm.currency")}</label>
              <select value={form.currency} onChange={set("currency")}>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="full">
              <label>{t("contractForm.notes")}</label>
              <textarea rows={4} value={form.notes} onChange={set("notes")} />
            </div>
          </div>

          {!editing && extraction && extraction.files.length > 0 && (
            <div className="muted" style={{ marginTop: 12 }}>
              {t("contractForm.filesToAttach")}: {extraction.files.map((f) => f.original_name).join(", ")}
            </div>
          )}

          <div style={{ marginTop: 18, display: "flex", gap: 10 }}>
            <button type="submit" disabled={busy || !form.title}>
              {editing ? t("contractForm.saveChanges") : t("contractForm.createContract")}
            </button>
            <button type="button" className="secondary" onClick={() => navigate(-1)}>
              {t("contractForm.cancel")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

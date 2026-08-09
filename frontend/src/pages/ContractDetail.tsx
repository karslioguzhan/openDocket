import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Contract, ContractFile } from "../types";
import { ExpiryLabel, StatusBadge, categoryLabel, formatBytes, valueLabel, CounterpartyChip } from "../components/ui";

export function ContractDetail() {
  const { id } = useParams() as { id: string };
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [contract, setContract] = useState<Contract | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shareEmail, setShareEmail] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    try {
      setContract(await api<Contract>(`/contracts/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("contractDetail.loadFailed"));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <div className="error">{error}</div>;
  if (!contract) return <div className="empty">{t("app.loading")}</div>;

  const isOwner = contract.role === "owner";

  const del = async () => {
    if (!confirm(t("contractDetail.moveToTrashConfirm"))) return;
    await api<void>(`/contracts/${id}`, { method: "DELETE" });
    navigate("/contracts");
  };

  const duplicate = async () => {
    const copy = await api<Contract>(`/contracts/${id}/duplicate`, { method: "POST" });
    navigate(`/contracts/${copy.id}`);
  };

  const reactivate = async () => {
    try {
      await api<Contract>(`/contracts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "active" }),
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("archive.reactivateFailed"));
    }
  };

  const archived = contract.status === "expired" || contract.status === "terminated";

  const addShare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shareEmail) return;
    try {
      await api<unknown>(`/contracts/${id}/shares`, {
        method: "POST",
        body: JSON.stringify({ email: shareEmail }),
      });
      setShareEmail("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("contractDetail.shareFailed"));
    }
  };

  const removeShare = async (userId: string) => {
    await api<void>(`/contracts/${id}/shares/${userId}`, { method: "DELETE" });
    await load();
  };

  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      await api<ContractFile>(`/contracts/${id}/files`, { method: "POST", body: form });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("contractDetail.uploadFailed"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const removeFile = async (fileId: string) => {
    if (!confirm(t("contractDetail.deleteFileConfirm"))) return;
    await api<void>(`/contracts/${id}/files/${fileId}`, { method: "DELETE" });
    await load();
  };

  return (
    <>
      <div className="page-header">
        <h1>{contract.title}</h1>
        <div style={{ display: "flex", gap: 10 }}>
          {isOwner && (
            <>
              <Link className="btn secondary" to={`/contracts/${id}/edit`}>
                {t("contractDetail.edit")}
              </Link>
              <button className="secondary" onClick={duplicate}>
                {t("contractDetail.duplicate")}
              </button>
              <button className="danger" onClick={del}>
                {t("contractDetail.trash")}
              </button>
            </>
          )}
        </div>
      </div>

      {!isOwner && <div className="card">{t("contractDetail.viewerAccess")}</div>}

      {archived && (
        <div className="archived-banner">
          <span className="badge">{t("archive.archived")}</span>
          <span>{t("archive.detailHint")}</span>
          {isOwner && (
            <button className="secondary" style={{ marginLeft: "auto" }} onClick={reactivate}>
              {t("archive.reactivate")}
            </button>
          )}
        </div>
      )}

      <div className="card">
        <div className="grid">
          <div className="stat">
            <div className="lbl">{t("common.status")}</div>
            <StatusBadge status={contract.status} />
          </div>
          {contract.counterparty && (
            <div className="stat">
              <div className="lbl">{t("common.counterparty")}</div>
              <div>{contract.counterparty.name}</div>
            </div>
          )}
          {contract.versicherungsnehmer && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.versicherungsnehmer")}</div>
              <CounterpartyChip name={contract.versicherungsnehmer.name} type={contract.versicherungsnehmer.type} />
            </div>
          )}
          {contract.versicherungsnummer && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.versicherungsnummer")}</div>
              <div>{contract.versicherungsnummer}</div>
            </div>
          )}
          {contract.category && (
            <div className="stat">
              <div className="lbl">{t("common.category")}</div>
              <div>{categoryLabel(t, contract.category)}</div>
            </div>
          )}
          {contract.effective_date && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.effectiveDate")}</div>
              <div>{new Date(contract.effective_date + "T00:00:00").toLocaleDateString(i18n.language)}</div>
            </div>
          )}
          {contract.expiry_date && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.expiryRenewal")}</div>
              <ExpiryLabel expiry={contract.expiry_date} />
            </div>
          )}
          {contract.value !== null && contract.value !== "" && (
            <div className="stat">
              <div className="lbl">{t("common.value")}</div>
              <div>{valueLabel(contract.value, contract.currency)}</div>
            </div>
          )}
          {contract.notice_days !== null && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.noticePeriod")}</div>
              <div>{t("noticeDays", { count: contract.notice_days })}</div>
            </div>
          )}
          {contract.tags.length > 0 && (
            <div className="stat">
              <div className="lbl">{t("contractDetail.tags")}</div>
              <div className="tags">
                {contract.tags.map((tg) => (
                  <span key={tg} className="tag">{tg}</span>
                ))}
              </div>
            </div>
          )}
        </div>
        {contract.notes && (
          <div style={{ marginTop: 16 }}>
            <div className="lbl" style={{ fontWeight: 600 }}>{t("contractDetail.notes")}</div>
            <p style={{ whiteSpace: "pre-wrap" }}>{contract.notes}</p>
          </div>
        )}
      </div>

      <div className="card">
        <h2>{t("contractDetail.files", { count: contract.files.length })}</h2>
        {contract.files.length > 0 && (
          <ul className="file-list">
            {contract.files.map((f) => (
              <li key={f.id}>
                <span>
                  <a href={`/api/contracts/${id}/files/${f.id}`} download={f.original_name}>
                    {f.original_name}
                  </a>{" "}
                  <span className="muted">
                    · {formatBytes(f.size_bytes)}
                  </span>
                </span>
                {isOwner && (
                  <button className="danger" style={{ padding: "4px 10px" }} onClick={() => removeFile(f.id)}>
                    {t("contractDetail.deleteFile")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {isOwner && (
          <label className="btn secondary" style={{ marginTop: 12, display: "inline-block", cursor: "pointer" }}>
            {uploading ? t("contractDetail.uploading") : t("contractDetail.uploadFile")}
            <input type="file" style={{ display: "none" }} onChange={upload} />
          </label>
        )}
      </div>

      {isOwner && (
        <div className="card">
          <h2>{t("contractDetail.sharedWith")}</h2>
          {contract.shares.length === 0 ? (
            <div className="muted">{t("contractDetail.notShared")}</div>
          ) : (
            <table>
              <tbody>
                {contract.shares.map((s) => (
                  <tr key={s.user_id}>
                    <td>{s.display_name ?? s.email}</td>
                    <td>{s.email}</td>
                    <td className="badge viewer">{t("role.viewer")}</td>
                    <td>
                      <button className="danger" style={{ padding: "4px 10px" }} onClick={() => removeShare(s.user_id)}>
                        {t("contractDetail.revoke")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <form onSubmit={addShare} style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <input
              type="email"
              placeholder={t("contractDetail.shareEmailPlaceholder")}
              value={shareEmail}
              onChange={(e) => setShareEmail(e.target.value)}
              style={{ maxWidth: 260 }}
            />
            <button type="submit">{t("contractDetail.share")}</button>
          </form>
        </div>
      )}
    </>
  );
}

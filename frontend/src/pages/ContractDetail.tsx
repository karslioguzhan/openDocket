import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import type { Contract, ContractFile } from "../types";
import { ExpiryLabel, StatusBadge, formatBytes, valueLabel } from "../components/ui";

export function ContractDetail() {
  const { id } = useParams() as { id: string };
  const navigate = useNavigate();
  const [contract, setContract] = useState<Contract | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shareEmail, setShareEmail] = useState("");
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    try {
      setContract(await api<Contract>(`/contracts/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <div className="error">{error}</div>;
  if (!contract) return <div className="empty">Loading…</div>;

  const isOwner = contract.role === "owner";

  const del = async () => {
    if (!confirm("Move this contract to trash?")) return;
    await api<void>(`/contracts/${id}`, { method: "DELETE" });
    navigate("/contracts");
  };

  const duplicate = async () => {
    const copy = await api<Contract>(`/contracts/${id}/duplicate`, { method: "POST" });
    navigate(`/contracts/${copy.id}`);
  };

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
      setError(err instanceof Error ? err.message : "Share failed");
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
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const removeFile = async (fileId: string) => {
    if (!confirm("Delete this file?")) return;
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
                Edit
              </Link>
              <button className="secondary" onClick={duplicate}>
                Duplicate
              </button>
              <button className="danger" onClick={del}>
                Trash
              </button>
            </>
          )}
        </div>
      </div>

      {!isOwner && <div className="card">You have <b>viewer</b> access to this contract.</div>}

      <div className="card">
        <div className="grid">
          <div className="stat">
            <div className="lbl">Status</div>
            <StatusBadge status={contract.status} />
          </div>
          <div className="stat">
            <div className="lbl">Counterparty</div>
            <div>{contract.counterparty?.name ?? "—"}</div>
          </div>
          <div className="stat">
            <div className="lbl">Category</div>
            <div>{contract.category?.name ?? "—"}</div>
          </div>
          <div className="stat">
            <div className="lbl">Effective date</div>
            <div>{contract.effective_date ?? "—"}</div>
          </div>
          <div className="stat">
            <div className="lbl">Expiry / renewal</div>
            <ExpiryLabel expiry={contract.expiry_date} />
          </div>
          <div className="stat">
            <div className="lbl">Value</div>
            <div>{valueLabel(contract.value, contract.currency) || "—"}</div>
          </div>
          <div className="stat">
            <div className="lbl">Notice period</div>
            <div>{contract.notice_days === null ? "—" : `${contract.notice_days} days`}</div>
          </div>
          <div className="stat">
            <div className="lbl">Tags</div>
            <div className="tags">
              {contract.tags.length ? contract.tags.map((t) => <span key={t} className="tag">{t}</span>) : "—"}
            </div>
          </div>
        </div>
        {contract.notes && (
          <div style={{ marginTop: 16 }}>
            <div className="lbl" style={{ fontWeight: 600 }}>Notes</div>
            <p style={{ whiteSpace: "pre-wrap" }}>{contract.notes}</p>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Files ({contract.files.length})</h2>
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
                    Delete
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {isOwner && (
          <label className="btn secondary" style={{ marginTop: 12, display: "inline-block", cursor: "pointer" }}>
            {uploading ? "Uploading…" : "Upload file"}
            <input type="file" style={{ display: "none" }} onChange={upload} />
          </label>
        )}
      </div>

      {isOwner && (
        <div className="card">
          <h2>Shared with</h2>
          {contract.shares.length === 0 ? (
            <div className="muted">Not shared with anyone.</div>
          ) : (
            <table>
              <tbody>
                {contract.shares.map((s) => (
                  <tr key={s.user_id}>
                    <td>{s.display_name ?? s.email}</td>
                    <td>{s.email}</td>
                    <td className="badge viewer">viewer</td>
                    <td>
                      <button className="danger" style={{ padding: "4px 10px" }} onClick={() => removeShare(s.user_id)}>
                        Revoke
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
              placeholder="user@example.com"
              value={shareEmail}
              onChange={(e) => setShareEmail(e.target.value)}
              style={{ maxWidth: 260 }}
            />
            <button type="submit">Share</button>
          </form>
        </div>
      )}
    </>
  );
}

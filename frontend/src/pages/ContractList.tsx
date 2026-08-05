import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { categoryLabel, ExpiryLabel, groupLabel, RoleBadge, valueLabel } from "../components/ui";
import type { CategoryMeta, Contract, ContractStatus } from "../types";

const STATUSES: Array<ContractStatus | ""> = ["", "draft", "active", "expired", "terminated"];

export function ContractList() {
  const { t } = useTranslation();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [categories, setCategories] = useState<CategoryMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | ContractStatus>("");
  const [category, setCategory] = useState("");
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    void api<CategoryMeta[]>("/meta/categories").then(setCategories);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const categoryGroups = categories.reduce<Record<string, CategoryMeta[]>>((acc, c) => {
    (acc[c.group] ??= []).push(c);
    return acc;
  }, {});

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (debounced) params.set("search", debounced);
      if (status) params.set("status", status);
      if (category) params.set("category", category);
      const rows = await api<Contract[]>(`/contracts?${params.toString()}`);
      setContracts(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("contracts.loadFailed"));
    }
  }, [debounced, status, category]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="page-header">
        <h1>{t("contracts.title")}</h1>
        <Link className="btn" to="/contracts/new">
          {t("contracts.newContract")}
        </Link>
      </div>

      <div className="card" style={{ display: "flex", gap: 12 }}>
        <input
          placeholder={t("contracts.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1 }}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value as ContractStatus)} style={{ width: 180 }}>
          {STATUSES.map((s) => (
            <option key={s || "all"} value={s}>
              {s === "" ? t("contracts.allStatuses") : t(`status.${s}`)}
            </option>
          ))}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 220 }}>
          <option value="">{t("contractForm.category")}</option>
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

      {error && <div className="error">{error}</div>}

      {contracts.length === 0 ? (
        <div className="card empty">{t("contracts.noContracts")}</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table>
            <thead>
              <tr>
                <th>{t("common.title")}</th>
                <th>{t("contractDetail.versicherungsnummer")}</th>
                <th>{t("common.status")}</th>
                <th>{t("common.counterparty")}</th>
                <th>{t("common.category")}</th>
                <th>{t("common.expiry")}</th>
                <th>{t("common.value")}</th>
                <th>{t("common.tags")}</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link to={`/contracts/${c.id}`}>{c.title}</Link> <RoleBadge role={c.role} />
                  </td>
                  <td>{c.versicherungsnummer ?? "—"}</td>
                  <td>
                    <span className={`badge ${c.status}`}>{t(`status.${c.status}`)}</span>
                  </td>
                  <td>{c.counterparty?.name ?? "—"}</td>
                  <td>{c.category ? categoryLabel(t, c.category) : "—"}</td>
                  <td>
                    <ExpiryLabel expiry={c.expiry_date} />
                  </td>
                  <td>{valueLabel(c.value, c.currency) || "—"}</td>
                  <td>
                    <div className="tags">
                      {c.tags.map((tg) => (
                        <span key={tg} className="tag">
                          {tg}
                        </span>
                      ))}
                    </div>
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

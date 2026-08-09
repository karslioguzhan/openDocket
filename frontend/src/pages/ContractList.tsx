import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { ContractCard } from "../components/ContractCard";
import { categoryLabel, DaysLeft, groupLabel } from "../components/ui";
import type { CategoryMeta, Contract, ContractStatus } from "../types";

const STATUSES: Array<ContractStatus | ""> = ["", "draft", "active", "expired", "terminated"];

interface Section {
  key: string;
  title: string;
  dotClass: string;
  contracts: Contract[];
}

export function ContractList() {
  const { t } = useTranslation();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [categories, setCategories] = useState<CategoryMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | ContractStatus>("");
  const [category, setCategory] = useState("");
  const [group, setGroup] = useState("");
  const [debounced, setDebounced] = useState("");
  const [archiveOpen, setArchiveOpen] = useState(false);

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
      if (group) params.set("group", group);
      else if (category) params.set("category", category);
      const rows = await api<Contract[]>(`/contracts?${params.toString()}`);
      setContracts(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("contracts.loadFailed"));
    }
  }, [debounced, status, group, category]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtering = Boolean(debounced || status || group || category);

  const expiringIds = new Set(
    contracts
      .filter((c) => c.status === "active" && c.expiry_date && (DaysLeft(c.expiry_date) ?? 91) <= 90)
      .map((c) => c.id),
  );

  const expiring = contracts.filter((c) => expiringIds.has(c.id));
  const active = contracts.filter((c) => c.status === "active" && !expiringIds.has(c.id));
  const draft = contracts.filter((c) => c.status === "draft");
  const archive = contracts.filter((c) => c.status === "expired" || c.status === "terminated");

  const sections: Section[] = [
    { key: "expiring", title: t("board.expiring"), dotClass: "dot-expiring", contracts: expiring },
    { key: "active", title: t("board.active"), dotClass: "dot-active", contracts: active },
    { key: "draft", title: t("board.draft"), dotClass: "dot-draft", contracts: draft },
  ].filter((s) => s.contracts.length > 0);

  const showArchive = filtering || archiveOpen;

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
        <select
          value={group ? `group:${group}` : category}
          onChange={(e) => {
            const val = e.target.value;
            if (val.startsWith("group:")) {
              setGroup(val.slice(6));
              setCategory("");
            } else {
              setCategory(val);
              setGroup("");
            }
          }}
          style={{ width: 260 }}
        >
          <option value="">{t("contractForm.category")}</option>
          {Object.entries(categoryGroups).map(([groupKey, cats]) => (
            <optgroup key={groupKey} label={groupLabel(t, groupKey)}>
              <option value={`group:${groupKey}`} style={{ fontWeight: 700 }}>
                {t("contracts.allGroup", { group: groupLabel(t, groupKey) })}
              </option>
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
        <>
          {sections.map((s) => (
            <div key={s.key} className="board-section">
              <div className="board-section-head">
                <span className={`dot ${s.dotClass}`} />
                <h2>{s.title}</h2>
                <span className="board-count">{s.contracts.length}</span>
              </div>
              <div className="board-grid">
                {s.contracts.map((c) => (
                  <ContractCard key={c.id} contract={c} />
                ))}
              </div>
            </div>
          ))}

          {archive.length > 0 && (
            <div className="board-section archive">
              <button
                type="button"
                className="board-section-head archive-toggle"
                onClick={() => setArchiveOpen((o) => !o)}
              >
                <span className="dot dot-archive" />
                <h2>{t("archive.title")}</h2>
                <span className="board-count">{archive.length}</span>
                <span className="archive-chevron">{showArchive ? "▾" : "▸"}</span>
              </button>
              {!showArchive && <p className="muted archive-hint">{t("archive.hint")}</p>}
              {showArchive && (
                <div className="board-grid">
                  {archive.map((c) => (
                    <ContractCard key={c.id} contract={c} />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}

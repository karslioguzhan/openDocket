import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Contract, Counterparty } from "../types";
import { CounterpartyChip, ExpiryLabel } from "../components/ui";

interface PersonRow {
  person: Counterparty;
  contracts: Contract[];
}

export function Versicherungsnehmer() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<PersonRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [counterparties, contracts] = await Promise.all([
        api<Counterparty[]>("/counterparties"),
        api<Contract[]>("/contracts"),
      ]);
      const persons = counterparties.filter((c) => c.type === "person");
      const byId = new Map<string, Contract[]>();
      for (const c of contracts) {
        const id = c.versicherungsnehmer?.id;
        if (!id) continue;
        const list = byId.get(id);
        if (list) list.push(c);
        else byId.set(id, [c]);
      }
      const grouped = persons
        .filter((person) => (byId.get(person.id)?.length ?? 0) > 0)
        .map((person) => ({ person, contracts: byId.get(person.id) ?? [] }))
        .sort(
          (a, b) =>
            b.contracts.length - a.contracts.length ||
            a.person.name.localeCompare(b.person.name),
        );
      setRows(grouped);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("versicherungsnehmer.loadFailed"));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="page-header">
        <h1>{t("versicherungsnehmer.title")}</h1>
      </div>
      {error && <div className="error">{error}</div>}
      {rows.length === 0 ? (
        <div className="card empty">{t("versicherungsnehmer.empty")}</div>
      ) : (
        rows.map(({ person, contracts }) => (
          <div key={person.id} className="card">
            <div className="vn-head">
              <CounterpartyChip name={person.name} type={person.type} />
              <span className="board-count">{contracts.length}</span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t("common.title")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("common.counterparty")}</th>
                  <th>{t("common.expiry")}</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link to={`/contracts/${c.id}`}>{c.title}</Link>
                    </td>
                    <td>
                      <span className={`badge ${c.status}`}>{t(`status.${c.status}`)}</span>
                    </td>
                    <td>{c.counterparty ? <CounterpartyChip name={c.counterparty.name} type={c.counterparty.type} /> : "—"}</td>
                    <td>
                      <ExpiryLabel expiry={c.expiry_date} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </>
  );
}

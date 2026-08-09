import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Contract } from "../types";
import { categoryLabel, ExpiryLabel, RoleBadge, valueLabel } from "./ui";

export function ContractCard({ contract }: { contract: Contract }) {
  const { t } = useTranslation();
  return (
    <div className="contract-card">
      <div className="contract-card-head">
        <Link to={`/contracts/${contract.id}`} className="contract-card-title">
          {contract.title}
        </Link>
        <RoleBadge role={contract.role} />
      </div>
      <div className="contract-card-meta">
        <span className={`badge ${contract.status}`}>{t(`status.${contract.status}`)}</span>
        {contract.counterparty && <span className="card-chip">{contract.counterparty.name}</span>}
        {contract.versicherungsnummer && <span className="card-chip muted">{contract.versicherungsnummer}</span>}
      </div>
      <div className="contract-card-fields">
        {contract.expiry_date && (
          <div className="card-row">
            <span className="card-label">{t("common.expiry")}</span>
            <ExpiryLabel expiry={contract.expiry_date} />
          </div>
        )}
        {contract.value !== null && (
          <div className="card-row">
            <span className="card-label">{t("common.value")}</span>
            <span>{valueLabel(contract.value, contract.currency)}</span>
          </div>
        )}
        {contract.category && (
          <div className="card-row">
            <span className="card-label">{t("common.category")}</span>
            <span>{categoryLabel(t, contract.category)}</span>
          </div>
        )}
      </div>
      {contract.tags.length > 0 && (
        <div className="tags">
          {contract.tags.map((tg) => (
            <span key={tg} className="tag">
              {tg}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

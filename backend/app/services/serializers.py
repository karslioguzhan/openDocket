from __future__ import annotations

from app.models import Contract
from app.schemas import (
    ContractOut,
    ContractFileOut,
    CounterpartyOut,
    ShareOut,
)


def contract_to_out(contract: Contract, include_shares: bool = True) -> ContractOut:
    role = getattr(contract, "_role", "owner")
    shares: list[ShareOut] = []
    if include_shares and role == "owner":
        shares = [
            ShareOut(
                id=s.id,
                user_id=s.user_id,
                email=s.user.email if s.user else "",
                display_name=s.user.display_name if s.user else None,
                role=s.role.value,
            )
            for s in contract.shares
        ]
    return ContractOut(
        id=contract.id,
        title=contract.title,
        status=contract.status,
        role=role,
        owner_id=contract.owner_id,
        counterparty=(
            CounterpartyOut.model_validate(contract.counterparty)
            if contract.counterparty is not None
            else None
        ),
        category=contract.category,
        tags=[t.name for t in contract.tags],
        effective_date=contract.effective_date,
        expiry_date=contract.expiry_date,
        notice_days=contract.notice_days,
        notes=contract.notes,
        value=contract.value,
        currency=contract.currency,
        files=[ContractFileOut.model_validate(f) for f in contract.files],
        shares=shares,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        deleted_at=contract.deleted_at,
    )

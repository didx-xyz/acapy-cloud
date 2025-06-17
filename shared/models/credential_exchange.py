from typing import Any, Literal, get_args

from aries_cloudcontroller import V20CredExRecord
from pydantic import BaseModel, Field

from shared.log_config import get_logger

logger = get_logger(__name__)

State = Literal[
    "proposal-sent",
    "proposal-received",
    "offer-sent",
    "offer-received",
    "request-sent",
    "request-received",
    "credential-issued",
    "credential-received",
    "credential-revoked",
    "abandoned",
    "done",
    "deleted",
]

Role = Literal["issuer", "holder"]


class CredentialExchange(BaseModel):
    # unused fields:
    # auto_offer: Optional[str] = None
    # auto_remove: Optional[str] = None
    # initiator: Optional[str] = None

    # Attributes can be None in proposed state
    attributes: dict[str, str] | None = None
    # Connection id can be None in connectionless exchanges
    connection_id: str | None = None
    created_at: str
    credential_definition_id: str | None = None
    credential_exchange_id: str = Field(...)
    did: str | None = None
    error_msg: str | None = None
    role: Role
    schema_id: str | None = None
    # state can be None in proposed state
    state: State | None = None
    # Thread id can be None in connectionless exchanges
    thread_id: str | None = None
    type: str = "anoncreds"
    updated_at: str | None = None


def credential_record_to_model_v2(record: V20CredExRecord) -> CredentialExchange:
    attributes = attributes_from_record_v2(record)
    schema_id, credential_definition_id = schema_cred_def_from_record(record)
    credential_exchange_id = f"v2-{record.cred_ex_id}"

    # Assume there is one credential type in the record
    cred_type = (
        next(iter(record.by_format.cred_offer.keys()))
        if record.by_format and record.by_format.cred_offer
        else "anoncreds"  # TODO: Fallback if cred_offer is not present
    )

    issuer_did = None
    # Attempt to retrieve issuer did from record, which is different for anoncreds vs ld_proof
    if record.by_format:
        match cred_type:
            case "anoncreds":  # In anoncreds, read issuer id from proposal
                if record.by_format.cred_proposal:  # Key safety check
                    cred_proposal = record.by_format.cred_proposal.get(cred_type, {})
                    issuer_did = cred_proposal.get("issuer_id")
            case "ld_proof":  # In ld_proofs, read issuer from credential offer
                if record.by_format.cred_offer:  # Key safety check
                    cred_offer = record.by_format.cred_offer.get(cred_type, {})
                    credential = cred_offer.get("credential", {})
                    issuer_did = credential.get("issuer")

        if cred_type == "ld_proof" and record.by_format and record.by_format.cred_offer:
            cred_offer = record.by_format.cred_offer.get(cred_type, {})
            credential = cred_offer.get("credential", {})
            issuer_did = credential.get("issuer")

    role = _validate_field(record.role, Role, "role")
    state = _validate_field(record.state, State, "state")

    return CredentialExchange(
        attributes=attributes,
        connection_id=record.connection_id,
        created_at=record.created_at,  # type: ignore
        credential_definition_id=credential_definition_id,
        credential_exchange_id=credential_exchange_id,
        did=issuer_did,
        error_msg=record.error_msg,
        role=role,  # type: ignore
        schema_id=schema_id,
        state=state,  # type: ignore
        thread_id=record.thread_id,
        updated_at=record.updated_at,
        type=cred_type,
    )


def _validate_field(
    record_field: str | None,
    field_type: Any,  # noqa: ANN401
    field_name: str,
) -> str | None:
    """Validate that a field is in the allowed values for a given type."""
    if record_field and record_field not in get_args(field_type):  # pragma: no cover
        logger.warning("Credential record has invalid {}: {}", field_name, record_field)
        return None
    return record_field


def schema_cred_def_from_record(
    record: V20CredExRecord,
) -> tuple[str | None, str | None]:
    if record.by_format and record.by_format.cred_offer:
        key = list(record.by_format.cred_offer.keys())
        if "ld_proof" in key:
            return None, None
        ex_record = record.by_format.cred_offer.get(key[0], {})
    elif record.by_format and record.by_format.cred_proposal:
        key = list(record.by_format.cred_proposal.keys())
        if "ld_proof" in key:
            return None, None
        ex_record = record.by_format.cred_proposal.get(key[0], {})
    else:
        ex_record = {}

    schema_id = ex_record.get("schema_id", None)
    credential_definition_id = ex_record.get("cred_def_id", None)

    return schema_id, credential_definition_id


def attributes_from_record_v2(record: V20CredExRecord) -> dict[str, str] | None:
    preview = None

    if record.cred_preview:
        preview = record.cred_preview
    elif record.cred_offer and record.cred_offer.credential_preview:
        preview = record.cred_offer.credential_preview
    elif record.cred_proposal and record.cred_proposal.credential_preview:
        preview = record.cred_proposal.credential_preview

    return {attr.name: attr.value for attr in preview.attributes} if preview else None

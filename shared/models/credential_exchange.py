from typing import Dict, Literal, Optional, Tuple

from aries_cloudcontroller import V20CredExRecord
from pydantic import BaseModel, Field

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
    attributes: Optional[Dict[str, str]] = None
    # Connection id can be None in connectionless exchanges
    connection_id: Optional[str] = None
    created_at: str
    credential_definition_id: Optional[str] = None
    credential_exchange_id: str = Field(...)
    did: Optional[str] = None
    error_msg: Optional[str] = None
    role: Role
    schema_id: Optional[str] = None
    # state can be None in proposed state
    state: Optional[State] = None
    # Thread id can be None in connectionless exchanges
    thread_id: Optional[str] = None
    type: str = "anoncreds"  # TODO: should come from the record
    updated_at: str


def credential_record_to_model_v2(record: V20CredExRecord) -> CredentialExchange:
    attributes = attributes_from_record_v2(record)
    schema_id, credential_definition_id = schema_cred_def_from_record(record)
    credential_exchange_id = f"v2-{record.cred_ex_id}"

    return CredentialExchange(
        attributes=attributes,
        connection_id=record.connection_id,
        created_at=record.created_at,
        credential_definition_id=credential_definition_id,
        credential_exchange_id=credential_exchange_id,
        did=(
            record.by_format.cred_offer["ld_proof"]["credential"]["issuer"]
            if record.by_format and "ld_proof" in record.by_format.cred_offer
            else None
        ),
        error_msg=record.error_msg,
        role=record.role,
        schema_id=schema_id,
        state=record.state,
        thread_id=record.thread_id,
        updated_at=record.updated_at,
        type=(
            list(record.by_format.cred_offer.keys())[0]
            if record.by_format
            else "anoncreds"
        ),
    )


def schema_cred_def_from_record(
    record: V20CredExRecord,
) -> Tuple[Optional[str], Optional[str]]:
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


def attributes_from_record_v2(record: V20CredExRecord) -> Optional[Dict[str, str]]:
    preview = None

    if record.cred_preview:
        preview = record.cred_preview
    elif record.cred_offer and record.cred_offer.credential_preview:
        preview = record.cred_offer.credential_preview
    elif record.cred_proposal and record.cred_proposal.credential_preview:
        preview = record.cred_proposal.credential_preview

    return {attr.name: attr.value for attr in preview.attributes} if preview else None

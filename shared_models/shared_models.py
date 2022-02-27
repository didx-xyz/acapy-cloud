from enum import Enum
from typing import Optional, Dict, Literal, Union, Tuple

from aries_cloudcontroller import (
    ConnRecord,
    IndyProof,
    IndyProofRequest,
    V10PresentationExchange,
    V10CredentialExchange,
    V20CredExRecord,
    V20PresExRecord,
    IndyProof,
)
from pydantic import BaseModel


class ProofRequestProtocolVersion(Enum):
    v1 = "v1"
    v2 = "v2"


class IssueCredentialProtocolVersion(Enum):
    v1 = "v1"
    v2 = "v2"


def pres_id_no_version(proof_id: str) -> str:
    if proof_id.startswith("v2-") or proof_id.startswith("v1-"):
        return proof_id[3:]
    else:
        raise ValueError("proof_id must start with prefix v1- or v2-")


def string_to_bool(verified: Optional[str]) -> Optional[bool]:
    if verified == "true":
        return True
    elif verified == "false":
        return False
    else:
        return None


def state_to_rfc_state(state: Optional[str]) -> Optional[str]:
    translation_dict = {
        "proposal_sent": "proposal-sent",
        "proposal_received": "proposal-received",
        "request_sent": "request-sent",
        "request_received": "request-received",
        "presentation_sent": "presentation-sent",
        "presentation_received": "presentation-received",
        "done": "done",
        "abandoned": "abandoned",
    }

    if not state or not state in translation_dict:
        return None

    return translation_dict[state]


class Connection(BaseModel):
    connection_id: str
    connection_protocol: Literal["connections/1.0", "didexchange/1.0"]
    created_at: str
    invitation_mode: Literal["once", "multi", "static"]
    their_role: Literal["invitee", "requester", "inviter", "responder"]
    state: str  # did-exchange state
    my_did: Optional[str]
    alias: Optional[str] = None
    their_did: Optional[str] = None
    their_label: Optional[str] = None
    their_public_did: Optional[str] = None
    updated_at: Optional[str] = None
    error_msg: Optional[str] = None
    invitation_key: Optional[str] = None
    invitation_msg_id: Optional[str] = None


class CredentialExchange(BaseModel):
    credential_id: str
    role: Literal["issuer", "holder"]
    created_at: str
    updated_at: str
    protocol_version: IssueCredentialProtocolVersion
    schema_id: Optional[str]
    credential_definition_id: Optional[str]
    state: Literal[
        "proposal-sent",
        "proposal-received",
        "offer-sent",
        "offer-received",
        "request-sent",
        "request-received",
        "credential-issued",
        "credential-received",
        "credential-acked",
        "done",
        "credential-acked",
    ]
    # Attributes can be None in proposed state
    attributes: Optional[Dict[str, str]] = None
    # Connetion id can be None in connectionless exchanges
    connection_id: Optional[str] = None


class PresentationExchange(BaseModel):
    connection_id: Optional[str] = None
    created_at: str
    proof_id: str
    presentation: Optional[IndyProof] = None
    presentation_request: Optional[IndyProofRequest] = None
    protocol_version: ProofRequestProtocolVersion
    role: Literal["prover", "verifier"]
    state: Literal[
        "proposal-sent",
        "proposal-received",
        "request-sent",
        "request-received",
        "presentation-sent",
        "presentation-received",
        "done",
        "abandoned",
    ]
    updated_at: Optional[str] = None
    verified: Optional[bool] = None


class TopicItem(BaseModel):
    topic: str
    wallet_id: str = None
    origin: str = None
    payload: dict


class HookBase(BaseModel):
    wallet_id: Optional[str]
    origin: Optional[str]


def presentation_record_to_model(
    record: Union[V20PresExRecord, V10PresentationExchange]
) -> PresentationExchange:
    if isinstance(record, V20PresExRecord):
        return PresentationExchange(
            connection_id=record.connection_id,
            created_at=record.created_at,
            protocol_version=ProofRequestProtocolVersion.v2.value,
            presentation=IndyProof(**record.by_format.pres["indy"])
            if record.by_format.pres
            else None,
            presentation_request=IndyProofRequest(
                **record.by_format.pres_request["indy"]
            ),
            proof_id="v2-" + str(record.pres_ex_id),
            role=record.role,
            state=record.state,
            updated_at=record.updated_at,
            verified=string_to_bool(record.verified),
        )
    elif isinstance(record, V10PresentationExchange):
        return PresentationExchange(
            connection_id=record.connection_id,
            created_at=record.created_at,
            presentation=record.presentation,
            presentation_request=record.presentation_request,
            protocol_version=ProofRequestProtocolVersion.v1.value,
            proof_id="v1-" + str(record.presentation_exchange_id),
            role=record.role,
            state=state_to_rfc_state(record.state),
            updated_at=record.updated_at,
            verified=string_to_bool(record.verified),
        )
    else:
        raise ValueError("Record format unknown.")


def conn_record_to_connection(connection_record: ConnRecord):
    return Connection(
        connection_id=connection_record.connection_id,
        connection_protocol=connection_record.connection_protocol,
        created_at=connection_record.created_at,
        invitation_mode=connection_record.invitation_mode,
        their_role=connection_record.their_role,
        my_did=connection_record.my_did,
        state=connection_record.rfc23_state,
        alias=connection_record.alias,
        their_did=connection_record.their_did,
        their_label=connection_record.their_label,
        their_public_did=connection_record.their_public_did,
        updated_at=connection_record.updated_at,
        error_msg=connection_record.error_msg,
        invitation_key=connection_record.invitation_key,
        invitation_msg_id=connection_record.invitation_msg_id,
    )


class ConnectionsHook(HookBase, Connection):
    pass


def credential_record_to_model_v1(record: V10CredentialExchange) -> CredentialExchange:
    attributes = attributes_from_record_v1(record)

    return CredentialExchange(
        credential_id=f"v1-{record.credential_exchange_id}",
        role=record.role,
        created_at=record.created_at,
        updated_at=record.updated_at,
        attributes=attributes,
        protocol_version=IssueCredentialProtocolVersion.v1,
        schema_id=record.schema_id,
        credential_definition_id=record.credential_definition_id,
        state=v1_state_to_rfc_state(record.state),
        connection_id=record.connection_id,
    )


def attributes_from_record_v1(
    record: V10CredentialExchange,
) -> Optional[Dict[str, str]]:
    preview = None

    if (
        record.credential_proposal_dict
        and record.credential_proposal_dict.credential_proposal
    ):
        preview = record.credential_proposal_dict.credential_proposal

    return {attr.name: attr.value for attr in preview.attributes} if preview else None


def v1_state_to_rfc_state(state: Optional[str]) -> Optional[str]:
    translation_dict = {
        "proposal_sent": "proposal-sent",
        "proposal_received": "proposal-received",
        "offer_sent": "offer-sent",
        "offer_received": "offer-received",
        "request_sent": "request-sent",
        "request_received": "request-received",
        "credential_issued": "credential-issued",
        "credential_received": "credential-received",
        "credential_acked": "credential-acked",
    }

    if not state or state not in translation_dict:
        return None

    return translation_dict[state]


def credential_record_to_model_v2(record: V20CredExRecord) -> CredentialExchange:
    attributes = attributes_from_record_v2(record)
    schema_id, credential_definition_id = schema_cred_def_from_record(record)

    return CredentialExchange(
        credential_id=f"v2-{record.cred_ex_id}",
        role=record.role,
        created_at=record.created_at,
        updated_at=record.updated_at,
        attributes=attributes,
        protocol_version=IssueCredentialProtocolVersion.v2,
        schema_id=schema_id,
        credential_definition_id=credential_definition_id,
        state=record.state,
        connection_id=record.connection_id,
    )


def schema_cred_def_from_record(
    record: V20CredExRecord,
) -> Tuple[Optional[str], Optional[str]]:
    schema_id = None
    credential_definition_id = None

    if record.by_format and record.by_format.cred_offer:
        indy = record.by_format.cred_offer.get("indy", {})
        schema_id = indy.get("schema_id", None)
        credential_definition_id = indy.get("cred_def_id", None)

    elif record.by_format and record.by_format.cred_proposal:
        indy = record.by_format.cred_proposal.get("indy", {})
        schema_id = indy.get("schema_id", None)
        credential_definition_id = indy.get("cred_def_id", None)

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

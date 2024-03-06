from typing import Dict, List, Optional

from aries_cloudcontroller import (
    IndyProof,
    IndyProofRequest,
    V20CredExRecordIndy,
    V20CredExRecordLDProof,
)
from pydantic import BaseModel, Field
from typing_extensions import Literal, TypedDict

from shared.models.protocol import (
    IssueCredentialProtocolVersion,
    PresentProofProtocolVersion,
)


class BasicMessage(BaseModel):
    connection_id: str
    content: str
    message_id: str
    sent_time: str
    state: Optional[Literal["received"]] = None


class Connection(BaseModel):
    # accept: Optional[str] = None
    alias: Optional[str] = None
    connection_id: Optional[str] = None
    connection_protocol: Optional[Literal["connections/1.0", "didexchange/1.0"]] = None
    created_at: Optional[str] = None
    error_msg: Optional[str] = None
    # inbound_connection_id
    invitation_key: Optional[str] = None
    invitation_mode: Optional[Literal["once", "multi", "static"]] = None
    invitation_msg_id: Optional[str] = None
    my_did: Optional[str] = None
    # request_id: Optional[str] = None
    # rfc23_state: Optional[str] = None
    state: Optional[str] = None
    their_did: Optional[str] = None
    their_label: Optional[str] = None
    their_public_did: Optional[str] = None
    their_role: Optional[Literal["invitee", "requester", "inviter", "responder"]] = None
    updated_at: Optional[str] = None


class CredentialExchange(BaseModel):
    # Attributes can be None in proposed state
    attributes: Optional[Dict[str, str]] = None
    # Connection id can be None in connectionless exchanges
    connection_id: Optional[str] = None
    created_at: str
    credential_definition_id: Optional[str] = None
    credential_id: str
    did: Optional[str] = None
    error_msg: Optional[str] = None
    protocol_version: IssueCredentialProtocolVersion
    role: Literal["issuer", "holder"]
    schema_id: Optional[str] = None
    # state can be None in proposed state
    state: Optional[
        Literal[
            "abandoned",
            "credential-issued",
            "credential-received",
            "done",
            "deleted",
            "offer-received",
            "offer-sent",
            "proposal-received",
            "proposal-sent",
            "request-received",
            "request-sent",
        ]
    ] = None
    # Thread id can be None in connectionless exchanges
    thread_id: Optional[str] = None
    type: str = "indy"
    updated_at: str


class PresentationExchange(BaseModel):
    connection_id: Optional[str] = None
    created_at: str
    error_msg: Optional[str] = None
    parent_thread_id: Optional[str] = None
    presentation: Optional[IndyProof] = None
    presentation_request: Optional[IndyProofRequest] = None
    proof_id: str
    protocol_version: PresentProofProtocolVersion
    role: Literal["prover", "verifier"]
    state: Optional[
        Literal[
            "abandoned",
            "done",
            "presentation-received",
            "presentation-sent",
            "proposal-received",
            "proposal-sent",
            "request-received",
            "request-sent",
            "abandoned",
            "deleted",
        ]
    ] = None
    thread_id: Optional[str] = None
    updated_at: Optional[str] = None
    verified: Optional[bool] = None


class DescriptionInfo(TypedDict):
    en: Optional[str]
    code: Optional[str]


class ProblemReport(BaseModel):
    type: Optional[str] = Field(None, alias="@type")
    id: Optional[str] = Field(None, alias="@id")
    thread: Optional[Dict[str, str]] = Field(None, alias="~thread")
    description: Optional[DescriptionInfo] = None
    problem_items: Optional[List[Dict[str, str]]] = None
    who_retries: Optional[str] = None
    fix_hint: Optional[Dict[str, str]] = None
    impact: Optional[str] = None
    where: Optional[str] = None
    noticed_time: Optional[str] = None
    tracking_uri: Optional[str] = None
    escalation_uri: Optional[str] = None


class CredExRecordLDProof(V20CredExRecordLDProof):
    pass  # renaming ACA-Py model


class CredExRecordIndy(V20CredExRecordIndy):
    pass  # renaming ACA-Py model


class DeletedCredential(BaseModel):
    id: str
    state: Literal["deleted"]

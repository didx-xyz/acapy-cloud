from typing import Literal

from aries_cloudcontroller import ConnRecord
from pydantic import BaseModel

State = Literal[
    "active",
    "response",
    "request",
    "start",
    "completed",
    "init",
    "error",
    "invitation",
    "abandoned",
]

Role = Literal["invitee", "requester", "inviter", "responder"]

Protocol = Literal["didexchange/1.0", "didexchange/1.1"]


class Connection(BaseModel):
    # accept: Optional[str] = None
    # inbound_connection_id: Optional[str] = None
    # request_id: Optional[str] = None
    # rfc23_state: Optional[str] = None

    alias: str | None = None
    connection_id: str | None = None
    connection_protocol: Protocol | None = None
    created_at: str | None = None
    error_msg: str | None = None
    invitation_key: str | None = None
    invitation_mode: Literal["once", "multi", "static"] | None = None
    invitation_msg_id: str | None = None
    my_did: str | None = None
    state: str | None = None  # not State Literal because we use rfc23_state
    their_did: str | None = None
    their_label: str | None = None
    their_public_did: str | None = None
    their_role: Role | None = None
    updated_at: str | None = None


def conn_record_to_connection(connection_record: ConnRecord):
    return Connection(
        alias=connection_record.alias,
        connection_id=connection_record.connection_id,
        connection_protocol=connection_record.connection_protocol,
        created_at=connection_record.created_at,
        error_msg=connection_record.error_msg,
        invitation_key=connection_record.invitation_key,
        invitation_mode=connection_record.invitation_mode,
        invitation_msg_id=connection_record.invitation_msg_id,
        my_did=connection_record.my_did,
        state=connection_record.rfc23_state,
        their_did=connection_record.their_did,
        their_label=connection_record.their_label,
        their_public_did=connection_record.their_public_did,
        their_role=connection_record.their_role,
        updated_at=connection_record.updated_at,
    )

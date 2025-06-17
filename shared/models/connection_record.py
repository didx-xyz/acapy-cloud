from typing import Literal, get_args

from aries_cloudcontroller import ConnRecord
from pydantic import BaseModel

from shared.log_config import get_logger

logger = get_logger(__name__)

Protocol = Literal["didexchange/1.0", "didexchange/1.1"]

InvitationMode = Literal["once", "multi", "static"]

Role = Literal["invitee", "requester", "inviter", "responder"]

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
    invitation_mode: InvitationMode | None = None
    invitation_msg_id: str | None = None
    my_did: str | None = None
    state: str | None = None  # not State Literal because we use rfc23_state
    their_did: str | None = None
    their_label: str | None = None
    their_public_did: str | None = None
    their_role: Role | None = None
    updated_at: str | None = None


def conn_record_to_connection(record: ConnRecord) -> Connection:
    # Role and State are typing.Literal types.
    # Check if record values are valid / match expected values.
    if record.connection_protocol and record.connection_protocol not in get_args(
        Protocol
    ):  # pragma: no cover
        logger.warning("Connection record has invalid connection protocol: {}", record)
        connection_protocol = None
    else:
        connection_protocol = record.connection_protocol

    if record.invitation_mode and record.invitation_mode not in get_args(
        InvitationMode
    ):  # pragma: no cover
        logger.warning("Connection record has invalid invitation mode: {}", record)
        invitation_mode = None
    else:
        invitation_mode = record.invitation_mode

    if record.their_role and record.their_role not in get_args(
        Role
    ):  # pragma: no cover
        logger.warning("Connection record has invalid their role: {}", record)
        their_role = None
    else:
        their_role = record.their_role

    if record.rfc23_state and record.rfc23_state not in get_args(
        State
    ):  # pragma: no cover
        logger.warning("Connection record has invalid state: {}", record)
        state = None
    else:
        state = record.rfc23_state

    return Connection(
        alias=record.alias,
        connection_id=record.connection_id,
        connection_protocol=connection_protocol,  # type: ignore
        created_at=record.created_at,
        error_msg=record.error_msg,
        invitation_key=record.invitation_key,
        invitation_mode=invitation_mode,  # type: ignore
        invitation_msg_id=record.invitation_msg_id,
        my_did=record.my_did,
        state=state,  # type: ignore
        their_did=record.their_did,
        their_label=record.their_label,
        their_public_did=record.their_public_did,
        their_role=their_role,  # type: ignore
        updated_at=record.updated_at,
    )

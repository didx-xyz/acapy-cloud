from typing import Any, Literal, get_args

from aries_cloudcontroller import ConnRecord
from pydantic import BaseModel

from shared.log_config import get_logger

logger = get_logger(__name__)

Protocol = Literal["didexchange/1.0", "didexchange/1.1"]

InvitationMode = Literal["once", "multi", "static"]

Role = Literal["invitee", "requester", "inviter", "responder"]

State = Literal[
    "start",
    "invitation-sent",
    "request-sent",
    "response-received",
    "completed",
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


def _truncate_did_peer_4(did: str | None) -> str | None:
    """Truncate did:peer:4 DIDs to short form (remove everything after and including 3rd colon)."""
    if did and did.startswith("did:peer:4"):
        parts = did.split(":")
        if len(parts) > 3:
            return ":".join(parts[:3])
    return did


def conn_record_to_connection(record: ConnRecord) -> Connection:
    # Role and State are typing.Literal types.
    # Check if record values are valid / match expected values.
    connection_protocol = _validate_field(
        record.connection_protocol, Protocol, "connection protocol"
    )
    invitation_mode = _validate_field(
        record.invitation_mode, InvitationMode, "invitation mode"
    )
    their_role = _validate_field(record.their_role, Role, "their role")
    state = _validate_field(record.rfc23_state, State, "state")

    return Connection(
        alias=record.alias,
        connection_id=record.connection_id,
        connection_protocol=connection_protocol,  # type: ignore
        created_at=record.created_at,
        error_msg=record.error_msg,
        invitation_key=record.invitation_key,
        invitation_mode=invitation_mode,  # type: ignore
        invitation_msg_id=record.invitation_msg_id,
        my_did=_truncate_did_peer_4(record.my_did),
        state=state,  # type: ignore
        their_did=_truncate_did_peer_4(record.their_did),
        their_label=record.their_label,
        their_public_did=record.their_public_did,
        their_role=their_role,  # type: ignore
        updated_at=record.updated_at,
    )


def _validate_field(
    record_field: str | None,
    field_type: Any,  # noqa: ANN401
    field_name: str,
) -> str | None:
    """Validate that a field is in the allowed values for a given type."""
    if record_field and record_field not in get_args(field_type):  # pragma: no cover
        logger.warning("Connection record has invalid {}: {}", field_name, record_field)
        return None
    return record_field

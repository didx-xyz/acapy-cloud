from typing import Literal, Optional, Union

from aries_cloudcontroller import (
    IndyProof,
    IndyProofRequest,
    V10PresentationExchange,
    V20PresExRecord,
)
from pydantic import BaseModel

from shared.log_config import get_logger
from shared.models.protocol import PresentProofProtocolVersion

logger = get_logger(__name__)

State = Literal[
    "abandoned",
    "done",
    "presentation-received",
    "presentation-sent",
    "proposal-received",
    "proposal-sent",
    "request-received",
    "request-sent",
    "deleted",
]

Role = Literal["prover", "verifier"]


class PresentationExchange(BaseModel):
    # auto_present: Optional[str] = None
    # auto_verify: Optional[str] = None
    # initiator: Optional[str] = None
    # trace: Optional[str] = None
    # presentation_exchange_id stored as proof_id instead

    connection_id: Optional[str] = None
    created_at: str
    error_msg: Optional[str] = None
    parent_thread_id: Optional[str] = None
    presentation: Optional[IndyProof] = None
    presentation_request: Optional[IndyProofRequest] = None
    proof_id: str
    protocol_version: PresentProofProtocolVersion
    role: Role
    state: Optional[State] = None
    thread_id: Optional[str] = None
    updated_at: Optional[str] = None
    verified: Optional[bool] = None


def presentation_record_to_model(
    record: Union[V20PresExRecord, V10PresentationExchange]
) -> PresentationExchange:
    if isinstance(record, V20PresExRecord):
        try:
            presentation = (
                IndyProof(**record.by_format.pres["indy"])
                if record.by_format.pres
                else None
            )
        except AttributeError:
            logger.info("Presentation record has no indy presentation")
            presentation = None

        try:
            presentation_request = IndyProofRequest(
                **record.by_format.pres_request["indy"]
            )
        except AttributeError:
            logger.info("Presentation record has no indy presentation request")
            presentation_request = None

        return PresentationExchange(
            connection_id=record.connection_id,
            created_at=record.created_at,
            error_msg=record.error_msg,
            parent_thread_id=record.pres_request.id if record.pres_request else None,
            presentation=presentation,
            presentation_request=presentation_request,
            proof_id="v2-" + str(record.pres_ex_id),
            protocol_version=PresentProofProtocolVersion.v2.value,
            role=record.role,
            state=record.state,
            thread_id=record.thread_id,
            updated_at=record.updated_at,
            verified=string_to_bool(record.verified),
        )

    elif isinstance(record, V10PresentationExchange):
        return PresentationExchange(
            connection_id=record.connection_id,
            created_at=record.created_at,
            error_msg=record.error_msg,
            parent_thread_id=(
                record.presentation_request_dict.id
                if record.presentation_request_dict
                else None
            ),
            presentation=record.presentation,
            presentation_request=record.presentation_request,
            proof_id="v1-" + str(record.presentation_exchange_id),
            protocol_version=PresentProofProtocolVersion.v1.value,
            role=record.role,
            state=v1_presentation_state_to_rfc_state(record.state),
            thread_id=record.thread_id,
            updated_at=record.updated_at,
            verified=string_to_bool(record.verified),
        )
    else:
        raise ValueError("Presentation record format unknown.")


def v1_presentation_state_to_rfc_state(state: Optional[str]) -> Optional[str]:
    translation_dict = {
        "abandoned": "abandoned",
        "deleted": "deleted",
        "done": "done",
        "presentation_acked": "done",
        "presentation_received": "presentation-received",
        "presentation_sent": "presentation-sent",
        "proposal_received": "proposal-received",
        "proposal_sent": "proposal-sent",
        "request_received": "request-received",
        "request_sent": "request-sent",
        "verified": "done",
    }

    if not state or state not in translation_dict:
        logger.warning("Presentation record has unknown state: {}", state)
        return None

    return translation_dict[state]


def back_to_v1_presentation_state(state: Optional[str]) -> Optional[str]:
    translation_dict = {
        "abandoned": "abandoned",
        "deleted": "deleted",
        "done": "verified",
        "presentation-received": "presentation_received",
        "presentation-sent": "presentation_sent",
        "proposal-received": "proposal_received",
        "proposal-sent": "proposal_sent",
        "request-received": "request_received",
        "request-sent": "request_sent",
    }

    return translation_dict[state]


def string_to_bool(verified: Optional[str]) -> Optional[bool]:
    if verified == "true":
        return True
    elif verified == "false":
        return False
    else:
        return None

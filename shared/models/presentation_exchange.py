from typing import Literal, Optional

from aries_cloudcontroller import V20Pres, V20PresExRecord, V20PresRequest
from pydantic import BaseModel

from shared.log_config import get_logger

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
    presentation: Optional[V20Pres] = None
    presentation_request: Optional[V20PresRequest] = None
    proof_id: str
    role: Role
    state: Optional[State] = None
    thread_id: Optional[str] = None
    updated_at: Optional[str] = None
    verified: Optional[bool] = None


def presentation_record_to_model(record: V20PresExRecord) -> PresentationExchange:
    presentation = None
    presentation_request = None

    if not record.by_format:
        logger.info("Presentation record has no by_format attribute: {}", record)
    else:
        if record.by_format.pres:
            # Get first key (we assume there is only one)
            key = next(iter(record.by_format.pres))
            presentation = record.by_format.pres[key]
        else:
            logger.debug("Presentation record has no presentation: {}", record)

        if record.by_format.pres_request:
            # Get first key (we assume there is only one)
            key = next(iter(record.by_format.pres_request))
            presentation_request = record.by_format.pres_request[key]
        else:
            logger.debug("Presentation record has no presentation request: {}", record)

    return PresentationExchange(
        connection_id=record.connection_id,
        created_at=record.created_at,
        error_msg=record.error_msg,
        parent_thread_id=record.pres_request.id if record.pres_request else None,
        presentation=presentation,
        presentation_request=presentation_request,
        proof_id="v2-" + str(record.pres_ex_id),
        role=record.role,
        state=record.state,
        thread_id=record.thread_id,
        updated_at=record.updated_at,
        verified=string_to_bool(record.verified),
    )


def string_to_bool(verified: Optional[str]) -> Optional[bool]:
    """Converts a string "true" or "false" to a boolean."""
    if verified == "true":
        return True
    elif verified == "false":
        return False
    else:
        return None

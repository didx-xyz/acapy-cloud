from typing import Literal, Optional

from aries_cloudcontroller import IndyProof, IndyProofRequest, V20PresExRecord
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
    presentation: Optional[IndyProof] = None
    presentation_request: Optional[IndyProofRequest] = None
    proof_id: str
    role: Role
    state: Optional[State] = None
    thread_id: Optional[str] = None
    updated_at: Optional[str] = None
    verified: Optional[bool] = None


def presentation_record_to_model(record: V20PresExRecord) -> PresentationExchange:
    if isinstance(record, V20PresExRecord):
        try:
            presentation = None
            if record.by_format.pres:
                key = list(record.by_format.pres.keys())[0]
                presentation = record.by_format.pres[key]

        except AttributeError:
            logger.info("Presentation record has no indy presentation")
            presentation = None

        try:
            presentation_request = None
            if record.by_format.pres_request:
                key = list(record.by_format.pres_request.keys())[0]
                presentation_request = record.by_format.pres_request[key]

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
            role=record.role,
            state=record.state,
            thread_id=record.thread_id,
            updated_at=record.updated_at,
            verified=string_to_bool(record.verified),
        )

    else:
        raise ValueError("Presentation record format unknown.")


def string_to_bool(verified: Optional[str]) -> Optional[bool]:
    if verified == "true":
        return True
    elif verified == "false":
        return False
    else:
        return None

from typing import Dict, List, Literal, Optional

from aries_cloudcontroller import (
    IndyEQProof,
    IndyGEProof,
    IndyGEProofPred,
    IndyNonRevocProof,
    IndyPrimaryProof,
    IndyProof,
    IndyProofIdentifier,
    IndyProofProof,
    IndyProofProofAggregatedProof,
    IndyProofProofProofsProof,
    IndyProofReqAttrSpec,
    IndyProofReqAttrSpecNonRevoked,
    IndyProofReqPredSpec,
    IndyProofReqPredSpecNonRevoked,
    IndyProofRequest,
    IndyProofRequestedProof,
    IndyProofRequestedProofPredicate,
    IndyProofRequestedProofRevealedAttr,
    IndyProofRequestedProofRevealedAttrGroup,
    IndyProofRequestNonRevoked,
    RawEncoded,
    V20PresExRecord,
)
from pydantic import BaseModel, Field, StrictStr

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


# The following models are just being renamed to avoid confusion with indy vs anoncreds


class EQProof(IndyEQProof):
    pass


class GEProofPred(IndyGEProofPred):
    attr_name: Optional[StrictStr] = Field(default=None, description="Attribute name")


class GEProof(IndyGEProof):
    predicate: Optional[GEProofPred] = None


class ProofProofAggregatedProof(IndyProofProofAggregatedProof):
    pass


class NonRevocProof(IndyNonRevocProof):
    pass


class PrimaryProof(IndyPrimaryProof):
    eq_proof: Optional[EQProof] = Field(default=None, description="Equality proof")
    ge_proofs: Optional[List[GEProof]] = Field(default=None, description="GE proofs")


class ProofProofProofsProof(IndyProofProofProofsProof):
    non_revoc_proof: Optional[NonRevocProof] = Field(
        default=None, description="Indy non-revocation proof"
    )
    primary_proof: Optional[PrimaryProof] = Field(
        default=None, description="Indy primary proof"
    )


class ProofProof(IndyProofProof):
    aggregated_proof: Optional[ProofProofAggregatedProof] = Field(
        default=None, description="Proof aggregated proof"
    )
    proofs: Optional[List[ProofProofProofsProof]] = Field(
        default=None, description="Proof proofs"
    )


class ProofRequestedProofPredicate(IndyProofRequestedProofPredicate):
    pass


class ProofRequestedProofRevealedAttrGroup(IndyProofRequestedProofRevealedAttrGroup):
    # Update description too
    values: Optional[Dict[str, RawEncoded]] = Field(
        default=None,
        description="Proof requested proof revealed attr groups group value",
    )


class ProofRequestedProofRevealedAttr(IndyProofRequestedProofRevealedAttr):
    pass


class ProofRequestedProof(IndyProofRequestedProof):
    predicates: Optional[Dict[str, ProofRequestedProofPredicate]] = Field(
        default=None, description="Proof requested proof predicates."
    )
    revealed_attr_groups: Optional[Dict[str, ProofRequestedProofRevealedAttrGroup]] = (
        Field(
            default=None, description="Proof requested proof revealed attribute groups"
        )
    )
    revealed_attrs: Optional[Dict[str, ProofRequestedProofRevealedAttr]] = Field(
        default=None, description="Proof requested proof revealed attributes"
    )


class ProofIdentifier(IndyProofIdentifier):
    pass


class Proof(IndyProof):
    identifiers: Optional[List[ProofIdentifier]] = Field(
        default=None, description="Proof.identifiers content"
    )
    proof: Optional[ProofProof] = Field(default=None, description="Proof.proof content")
    requested_proof: Optional[ProofRequestedProof] = Field(
        default=None, description="Proof.requested_proof content"
    )


class ProofRequestNonRevoked(IndyProofRequestNonRevoked):
    pass


class ProofReqPredSpecNonRevoked(IndyProofReqPredSpecNonRevoked):
    pass


class ProofReqPredSpec(IndyProofReqPredSpec):
    non_revoked: Optional[ProofReqPredSpecNonRevoked] = None


class ProofReqAttrSpecNonRevoked(IndyProofReqAttrSpecNonRevoked):
    pass


class ProofReqAttrSpec(IndyProofReqAttrSpec):
    non_revoked: Optional[ProofReqAttrSpecNonRevoked] = None


class ProofRequest(IndyProofRequest):
    non_revoked: Optional[ProofRequestNonRevoked] = None
    requested_attributes: Dict[str, ProofReqAttrSpec] = Field(
        description="Requested attribute specifications of proof request"
    )
    requested_predicates: Dict[str, ProofReqPredSpec] = Field(
        description="Requested predicate specifications of proof request"
    )


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
    presentation: Optional[Proof] = None
    presentation_request: Optional[ProofRequest] = None
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
        proof_id=f"v2-{record.pres_ex_id}",
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

from typing import Literal

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
    attr_name: StrictStr | None = Field(default=None, description="Attribute name")


class GEProof(IndyGEProof):
    predicate: GEProofPred | None = None


class ProofProofAggregatedProof(IndyProofProofAggregatedProof):
    pass


class NonRevocProof(IndyNonRevocProof):
    pass


class PrimaryProof(IndyPrimaryProof):
    eq_proof: EQProof | None = Field(default=None, description="Equality proof")
    ge_proofs: list[GEProof] | None = Field(default=None, description="GE proofs")


class ProofProofProofsProof(IndyProofProofProofsProof):
    non_revoc_proof: NonRevocProof | None = Field(
        default=None, description="Non-revocation proof"
    )
    primary_proof: PrimaryProof | None = Field(
        default=None, description="Primary proof"
    )


class ProofProof(IndyProofProof):
    aggregated_proof: ProofProofAggregatedProof | None = Field(
        default=None, description="Proof aggregated proof"
    )
    proofs: list[ProofProofProofsProof] | None = Field(
        default=None, description="Proof proofs"
    )


class ProofRequestedProofPredicate(IndyProofRequestedProofPredicate):
    pass


class ProofRequestedProofRevealedAttrGroup(IndyProofRequestedProofRevealedAttrGroup):
    # Update description too
    values: dict[str, RawEncoded] | None = Field(
        default=None,
        description="Proof requested proof revealed attr groups group value",
    )


class ProofRequestedProofRevealedAttr(IndyProofRequestedProofRevealedAttr):
    pass


class ProofRequestedProof(IndyProofRequestedProof):
    predicates: dict[str, ProofRequestedProofPredicate] | None = Field(
        default=None, description="Proof requested proof predicates."
    )
    revealed_attr_groups: dict[str, ProofRequestedProofRevealedAttrGroup] | None = (
        Field(
            default=None, description="Proof requested proof revealed attribute groups"
        )
    )
    revealed_attrs: dict[str, ProofRequestedProofRevealedAttr] | None = Field(
        default=None, description="Proof requested proof revealed attributes"
    )


class ProofIdentifier(IndyProofIdentifier):
    pass


class Proof(IndyProof):
    identifiers: list[ProofIdentifier] | None = Field(
        default=None, description="Proof.identifiers content"
    )
    proof: ProofProof | None = Field(default=None, description="Proof.proof content")
    requested_proof: ProofRequestedProof | None = Field(
        default=None, description="Proof.requested_proof content"
    )


class ProofRequestNonRevoked(IndyProofRequestNonRevoked):
    pass


class ProofReqPredSpecNonRevoked(IndyProofReqPredSpecNonRevoked):
    pass


class ProofReqPredSpec(IndyProofReqPredSpec):
    non_revoked: ProofReqPredSpecNonRevoked | None = None


class ProofReqAttrSpecNonRevoked(IndyProofReqAttrSpecNonRevoked):
    pass


class ProofReqAttrSpec(IndyProofReqAttrSpec):
    non_revoked: ProofReqAttrSpecNonRevoked | None = None


class ProofRequest(IndyProofRequest):
    non_revoked: ProofRequestNonRevoked | None = None
    requested_attributes: dict[str, ProofReqAttrSpec] = Field(
        description="Requested attribute specifications of proof request"
    )
    requested_predicates: dict[str, ProofReqPredSpec] = Field(
        description="Requested predicate specifications of proof request"
    )


class PresentationExchange(BaseModel):
    # auto_present: Optional[str] = None
    # auto_verify: Optional[str] = None
    # initiator: Optional[str] = None
    # trace: Optional[str] = None
    # presentation_exchange_id stored as proof_id instead

    connection_id: str | None = None
    created_at: str
    error_msg: str | None = None
    parent_thread_id: str | None = None
    presentation: Proof | None = None
    presentation_request: ProofRequest | None = None
    proof_id: str
    role: Role
    state: State | None = None
    thread_id: str | None = None
    updated_at: str | None = None
    verified: bool | None = None


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


def string_to_bool(verified: str | None) -> bool | None:
    """Converts a string "true" or "false" to a boolean."""
    if verified == "true":
        return True
    elif verified == "false":
        return False
    else:
        return None

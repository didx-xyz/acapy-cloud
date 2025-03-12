import pytest
from aries_cloudcontroller import DIFProofRequest, PresentationDefinition

from app.models.verifier import (
    AcceptProofRequest,
    AnoncredsPresentationRequest,
    DIFPresSpec,
    IndyPresSpec,
    IndyProofRequest,
    ProofRequestBase,
    ProofRequestType,
    RejectProofRequest,
)
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_proof_request_base_model():
    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(type=ProofRequestType.INDY, indy_proof_request=None)
    assert exc.value.detail == (
        "indy_proof_request must be populated if `indy` type is selected"
    )
    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(type=ProofRequestType.ANONCREDS, anoncreds_proof_request=None)
    assert exc.value.detail == (
        "anoncreds_proof_request must be populated if `anoncreds` type is selected"
    )
    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(
            type=ProofRequestType.LD_PROOF,
            indy_proof_request=IndyProofRequest(
                requested_attributes={}, requested_predicates={}
            ),
            dif_proof_request=DIFProofRequest(
                presentation_definition=PresentationDefinition()
            ),
        )
    assert exc.value.detail == (
        "Only dif_proof_request must not be populated if `ld_proof` type is selected"
    )

    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(
            type=ProofRequestType.INDY,
            indy_proof_request=IndyProofRequest(
                requested_attributes={}, requested_predicates={}
            ),
            dif_proof_request=DIFProofRequest(
                presentation_definition=PresentationDefinition()
            ),
        )
    assert exc.value.detail == (
        "Only indy_proof_request must not be populated if `indy` type is selected"
    )

    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(
            type=ProofRequestType.ANONCREDS,
            anoncreds_proof_request=AnoncredsPresentationRequest(
                requested_attributes={}, requested_predicates={}
            ),
            dif_proof_request=DIFProofRequest(
                presentation_definition=PresentationDefinition()
            ),
        )
    assert exc.value.detail == (
        "Only anoncreds_proof_request must not be populated if `anoncreds` type is selected"
    )

    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(type=ProofRequestType.LD_PROOF, dif_proof_request=None)
    assert exc.value.detail == (
        "dif_proof_request must be populated if `ld_proof` type is selected"
    )

    ProofRequestBase.check_proof_request(
        values=ProofRequestBase(
            indy_proof_request=IndyProofRequest(
                requested_attributes={}, requested_predicates={}
            )
        )
    )


def test_accept_proof_request_model():
    AcceptProofRequest(
        proof_id="abc",
        indy_presentation_spec=IndyPresSpec(
            requested_attributes={},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    AcceptProofRequest(
        proof_id="abc",
        type=ProofRequestType.LD_PROOF,
        dif_presentation_spec=DIFPresSpec(),
    )

    AcceptProofRequest(
        proof_id="abc",
        anoncreds_presentation_spec=IndyPresSpec(
            requested_attributes={},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    with pytest.raises(CloudApiValueError) as exc:
        AcceptProofRequest(type=ProofRequestType.INDY, indy_presentation_spec=None)
    assert exc.value.detail == (
        "indy_presentation_spec must be populated if `indy` type is selected"
    )
    with pytest.raises(CloudApiValueError) as exc:
        AcceptProofRequest(type=ProofRequestType.LD_PROOF, dif_presentation_spec=None)
    assert exc.value.detail == (
        "dif_presentation_spec must be populated if `ld_proof` type is selected"
    )
    with pytest.raises(CloudApiValueError) as exc:
        AcceptProofRequest(
            type=ProofRequestType.ANONCREDS, anoncreds_presentation_spec=None
        )
    assert exc.value.detail == (
        "anoncreds_proof_request must be populated if `anoncreds` type is selected"
    )


def test_reject_proof_request_model():
    RejectProofRequest(proof_id="abc", problem_report="valid message")

    with pytest.raises(CloudApiValueError) as exc:
        RejectProofRequest(proof_id="abc", problem_report="")

    assert exc.value.detail == "problem_report cannot be an empty string"

import pytest
from aries_cloudcontroller import DIFProofRequest, PresentationDefinition

from app.models.verifier import (
    AcceptProofRequest,
    AnonCredsPresentationRequest,
    AnonCredsPresSpec,
    DIFPresSpec,
    ProofRequestBase,
    RejectProofRequest,
)
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_proof_request_base_model() -> None:
    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(anoncreds_proof_request=None)
    assert exc.value.detail == (
        "One of anoncreds_proof_request or dif_proof_request must be populated"
    )
    with pytest.raises(CloudApiValueError) as exc:
        ProofRequestBase(
            anoncreds_proof_request=AnonCredsPresentationRequest(
                requested_attributes={}, requested_predicates={}
            ),
            dif_proof_request=DIFProofRequest(
                presentation_definition=PresentationDefinition()
            ),
        )
    assert exc.value.detail == (
        "Only one of anoncreds_proof_request or dif_proof_request must be populated"
    )

    ProofRequestBase(
        anoncreds_proof_request=AnonCredsPresentationRequest(
            requested_attributes={}, requested_predicates={}
        ),
    )


def test_accept_proof_request_model() -> None:
    AcceptProofRequest(
        proof_id="abc",
        dif_presentation_spec=DIFPresSpec(),
    )

    AcceptProofRequest(
        proof_id="abc",
        anoncreds_presentation_spec=AnonCredsPresSpec(
            requested_attributes={},
            requested_predicates={},
            self_attested_attributes={},
        ),
    )

    with pytest.raises(CloudApiValueError) as exc:
        AcceptProofRequest(
            dif_presentation_spec=None,
            proof_id="abc",
        )
    assert exc.value.detail == (
        "One of anoncreds_presentation_spec or dif_presentation_spec must be populated"
    )
    with pytest.raises(CloudApiValueError) as exc:
        AcceptProofRequest(
            anoncreds_presentation_spec=AnonCredsPresSpec(
                name="abc",
                version="1.0",
                requested_attributes={},
                requested_predicates={},
                self_attested_attributes={},
            ),
            dif_presentation_spec=DIFPresSpec(),
            proof_id="abc",
        )
    assert exc.value.detail == (
        "Only one of anoncreds_presentation_spec or dif_presentation_spec must be populated"
    )


def test_reject_proof_request_model() -> None:
    RejectProofRequest(proof_id="abc", problem_report="valid message")

    with pytest.raises(CloudApiValueError) as exc:
        RejectProofRequest(proof_id="abc", problem_report="")

    assert exc.value.detail == "problem_report cannot be an empty string"

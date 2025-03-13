from aries_cloudcontroller import (
    IndyProof,
    IndyProofProof,
    IndyProofRequest,
    V20PresExRecord,
    V20PresExRecordByFormat,
)

from shared.models.presentation_exchange import (
    PresentationExchange,
    presentation_record_to_model,
    string_to_bool,
)


def test_presentation_exchange_model():
    # Test creating a PresentationExchange instance
    exchange = PresentationExchange(
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        error_msg=None,
        parent_thread_id="parent-thread-id",
        presentation=IndyProof(proof=IndyProofProof()),
        presentation_request=IndyProofRequest(
            name="request",
            requested_attributes={},
            requested_predicates={},
        ),
        proof_id="proof-id",
        role="prover",
        state="presentation-received",
        thread_id="thread-id",
        updated_at="2023-01-01T01:00:00Z",
        verified=True,
    )

    assert exchange.connection_id == "conn-id"
    assert exchange.created_at == "2023-01-01T00:00:00Z"
    assert exchange.error_msg is None
    assert exchange.parent_thread_id == "parent-thread-id"
    assert exchange.presentation == IndyProof(proof=IndyProofProof())
    assert exchange.presentation_request == IndyProofRequest(
        name="request",
        requested_attributes={},
        requested_predicates={},
    )
    assert exchange.proof_id == "proof-id"
    assert exchange.role == "prover"
    assert exchange.state == "presentation-received"
    assert exchange.thread_id == "thread-id"
    assert exchange.updated_at == "2023-01-01T01:00:00Z"
    assert exchange.verified is True


def test_presentation_record_to_model():
    # Mock a V20PresExRecord
    record = V20PresExRecord(
        pres_ex_id="pres-ex-id",
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        role="prover",
        state="presentation-received",
        thread_id="thread-id",
        updated_at="2023-01-01T01:00:00Z",
        verified="true",
        by_format={
            "pres": {"indy": IndyProof(proof=IndyProofProof())},
            "pres_request": {
                "indy": IndyProofRequest(
                    name="request",
                    requested_attributes={},
                    requested_predicates={},
                )
            },
        },
    )

    model = presentation_record_to_model(record)

    assert model.proof_id == "v2-pres-ex-id"
    assert model.presentation == IndyProof(proof=IndyProofProof())
    assert model.presentation_request == IndyProofRequest(
        name="request",
        requested_attributes={},
        requested_predicates={},
    )
    assert model.connection_id == "conn-id"
    assert model.created_at == "2023-01-01T00:00:00Z"
    assert model.role == "prover"
    assert model.state == "presentation-received"
    assert model.thread_id == "thread-id"
    assert model.updated_at == "2023-01-01T01:00:00Z"
    assert model.verified is True


def test_presentation_record_to_model_no_by_format():
    # Test with a record having no by_format
    record = V20PresExRecord(
        pres_ex_id="pres-ex-id",
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        role="prover",
        state="presentation-received",
        thread_id="thread-id",
        updated_at="2023-01-01T01:00:00Z",
        verified="false",
    )

    model = presentation_record_to_model(record)

    assert model.proof_id == "v2-pres-ex-id"
    assert model.presentation is None
    assert model.presentation_request is None
    assert model.connection_id == "conn-id"
    assert model.created_at == "2023-01-01T00:00:00Z"
    assert model.role == "prover"
    assert model.state == "presentation-received"
    assert model.thread_id == "thread-id"
    assert model.updated_at == "2023-01-01T01:00:00Z"
    assert model.verified is False


def test_presentation_record_to_model_empty_by_format():
    # Test with a record having no by_format
    record = V20PresExRecord(
        pres_ex_id="pres-ex-id",
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        role="prover",
        state="presentation-received",
        thread_id="thread-id",
        updated_at="2023-01-01T01:00:00Z",
        verified="false",
        by_format=V20PresExRecordByFormat(),
    )

    model = presentation_record_to_model(record)

    assert model.proof_id == "v2-pres-ex-id"
    assert model.presentation is None
    assert model.presentation_request is None
    assert model.connection_id == "conn-id"
    assert model.created_at == "2023-01-01T00:00:00Z"
    assert model.role == "prover"
    assert model.state == "presentation-received"
    assert model.thread_id == "thread-id"
    assert model.updated_at == "2023-01-01T01:00:00Z"
    assert model.verified is False


def test_string_to_bool():
    assert string_to_bool("true") is True
    assert string_to_bool("false") is False
    assert string_to_bool(None) is None
    assert string_to_bool("random") is None

import pytest
from aries_cloudcontroller import (
    V20CredAttrSpec,
    V20CredExRecord,
    V20CredFormat,
    V20CredOffer,
    V20CredPreview,
    V20CredProposal,
)

from shared.models.credential_exchange import (
    CredentialExchange,
    attributes_from_record_v2,
    credential_record_to_model_v2,
    schema_cred_def_from_record,
)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")  # credential_id is deprecated
def test_credential_exchange_model():
    # Test creating a CredentialExchange instance
    exchange = CredentialExchange(
        attributes={"name": "Alice"},
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        credential_definition_id="cred-def-id",
        credential_id="cred-id",
        credential_exchange_id="cred-ex-id",
        did="did:sov:123",
        error_msg=None,
        role="issuer",
        schema_id="schema-id",
        state="offer-sent",
        thread_id="thread-id",
        type="indy",
        updated_at="2023-01-01T01:00:00Z",
    )

    assert exchange.attributes == {"name": "Alice"}
    assert exchange.connection_id == "conn-id"
    assert exchange.created_at == "2023-01-01T00:00:00Z"
    assert exchange.credential_definition_id == "cred-def-id"
    assert exchange.credential_id == "cred-id"
    assert exchange.credential_exchange_id == "cred-ex-id"
    assert exchange.did == "did:sov:123"
    assert exchange.error_msg is None
    assert exchange.role == "issuer"
    assert exchange.schema_id == "schema-id"
    assert exchange.state == "offer-sent"
    assert exchange.thread_id == "thread-id"
    assert exchange.type == "indy"
    assert exchange.updated_at == "2023-01-01T01:00:00Z"


def test_credential_record_to_model_v2():
    # Mock a V20CredExRecord
    record = V20CredExRecord(
        cred_ex_id="cred-ex-id",
        connection_id="conn-id",
        created_at="2023-01-01T00:00:00Z",
        role="issuer",
        state="offer-sent",
        thread_id="thread-id",
        updated_at="2023-01-01T01:00:00Z",
        cred_preview=V20CredPreview(
            attributes=[
                V20CredAttrSpec(name="name", value="Alice"),
                V20CredAttrSpec(name="age", value="30"),
            ]
        ),
        by_format=None,
    )

    model = credential_record_to_model_v2(record)

    assert model.credential_exchange_id == "v2-cred-ex-id"
    assert model.attributes == {"name": "Alice", "age": "30"}
    assert model.connection_id == "conn-id"
    assert model.created_at == "2023-01-01T00:00:00Z"
    assert model.role == "issuer"
    assert model.state == "offer-sent"
    assert model.thread_id == "thread-id"
    assert model.updated_at == "2023-01-01T01:00:00Z"
    assert model.type == "indy"


def test_schema_cred_def_from_record():
    # Test with a record having cred_offer
    record = V20CredExRecord(
        by_format={
            "cred_offer": {
                "indy": {
                    "schema_id": "schema-id",
                    "cred_def_id": "cred-def-id",
                }
            }
        }
    )

    schema_id, cred_def_id = schema_cred_def_from_record(record)
    assert schema_id == "schema-id"
    assert cred_def_id == "cred-def-id"

    # Test with a record having cred_proposal
    record = V20CredExRecord(
        by_format={
            "cred_proposal": {
                "indy": {
                    "schema_id": "schema-id",
                    "cred_def_id": "cred-def-id",
                }
            }
        }
    )

    schema_id, cred_def_id = schema_cred_def_from_record(record)
    assert schema_id == "schema-id"
    assert cred_def_id == "cred-def-id"

    # Test with a record having offer and ld_proof
    record = V20CredExRecord(by_format={"cred_offer": {"ld_proof": {}}})

    schema_id, cred_def_id = schema_cred_def_from_record(record)
    assert schema_id is None
    assert cred_def_id is None

    # Test with a record having proposal and ld_proof
    record = V20CredExRecord(by_format={"cred_proposal": {"ld_proof": {}}})

    schema_id, cred_def_id = schema_cred_def_from_record(record)
    assert schema_id is None
    assert cred_def_id is None


def test_attributes_from_record_v2():
    # Test with cred_preview
    record = V20CredExRecord(
        cred_preview=V20CredPreview(
            attributes=[
                V20CredAttrSpec(name="name", value="Alice"),
                V20CredAttrSpec(name="age", value="30"),
            ]
        )
    )

    attributes = attributes_from_record_v2(record)
    assert attributes == {"name": "Alice", "age": "30"}

    # Test with cred_offer having credential_preview
    record = V20CredExRecord(
        cred_offer=V20CredOffer(
            credential_preview=V20CredPreview(
                attributes=[
                    V20CredAttrSpec(name="name", value="Bob"),
                    V20CredAttrSpec(name="age", value="40"),
                ]
            ),
            formats=[V20CredFormat(format="indy", attach_id="attach_id")],
            offersattach=[],
        ),
    )

    attributes = attributes_from_record_v2(record)
    assert attributes == {"name": "Bob", "age": "40"}

    # Test with cred_proposal having credential_preview
    record = V20CredExRecord(
        cred_proposal=V20CredProposal(
            credential_preview=V20CredPreview(
                attributes=[
                    V20CredAttrSpec(name="name", value="Charlie"),
                    V20CredAttrSpec(name="age", value="50"),
                ]
            ),
            formats=[V20CredFormat(format="indy", attach_id="attach_id")],
            filtersattach=[],
        )
    )

    attributes = attributes_from_record_v2(record)
    assert attributes == {"name": "Charlie", "age": "50"}

    # Test with no attributes
    record = V20CredExRecord()
    attributes = attributes_from_record_v2(record)
    assert attributes is None

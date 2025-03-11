import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from aries_cloudcontroller import AdminConfig, TransactionRecord

from endorser.services.endorser_config import EndorserConfig
from endorser.util.transaction_record import (
    get_did_and_schema_id_from_cred_def_attachment,
    get_endorsement_request_attachment,
    is_credential_definition_transaction,
)
from shared.models.endorsement import TransactionTypes


def test_get_endorsement_request_attachment_with_valid_attachment():
    transaction_record_with_attachment = TransactionRecord(
        messages_attach=[
            {
                "data": {
                    "json": json.dumps(
                        {
                            "identifier": "identifier_value",
                            "operation": {"type": "102", "ref": "ref_value"},
                        }
                    )
                }
            }
        ]
    )
    attachment = get_endorsement_request_attachment(transaction_record_with_attachment)
    assert attachment == {
        "identifier": "identifier_value",
        "operation": {"type": "102", "ref": "ref_value"},
    }


def test_get_endorsement_request_attachment_without_attachment():
    transaction_record_without_attachment = TransactionRecord(messages_attach=[])
    attachment = get_endorsement_request_attachment(
        transaction_record_without_attachment
    )
    assert attachment is None

    transaction_record_data_key = TransactionRecord(
        messages_attach=[{"not_the_expected_data_key": "abc"}]
    )
    attachment = get_endorsement_request_attachment(transaction_record_data_key)
    assert attachment is None

    transaction_record_without_json_key = TransactionRecord(
        messages_attach=[{"data": {"not_the_expected_json_key": "abc"}}]
    )
    attachment = get_endorsement_request_attachment(transaction_record_without_json_key)
    assert attachment is None


def test_get_endorsement_request_attachment_invalid_json():
    transaction_record_without_valid_json = TransactionRecord(
        messages_attach=[{"data": {"json": "invalid_json"}}]
    )
    attachment = get_endorsement_request_attachment(
        transaction_record_without_valid_json
    )
    assert attachment is None


def test_get_endorsement_request_attachment_exception():
    # Mock a TransactionRecord that raises a KeyError when messages_attach is accessed
    transaction_record_exception = MagicMock()
    transaction_record_exception.messages_attach = Mock(
        side_effect=KeyError("Key error exception")
    )

    attachment = get_endorsement_request_attachment(transaction_record_exception)
    assert attachment is None


def test_is_credential_definition_transaction_true():
    operation_type = TransactionTypes.CLAIM_DEF
    assert (
        is_credential_definition_transaction(
            operation_type,
            attachment={
                "identifier": "identifier_value",
                "operation": {"ref": "ref_value"},
            },
        )
        is True
    )


def test_is_credential_definition_transaction_false():
    operation_type = "100"
    assert is_credential_definition_transaction(operation_type, attachment={}) is False


def test_is_credential_definition_transaction_exception():
    attachment = MagicMock(side_effect=KeyError("Exception"))

    assert (
        is_credential_definition_transaction(
            operation_type=TransactionTypes.CLAIM_DEF, attachment=attachment
        )
        is False
    )


@pytest.mark.anyio
async def test_get_did_and_schema_id_from_cred_def_attachment(mock_acapy_client):
    mock_acapy_client.schema.get_schema.return_value = MagicMock(
        var_schema=MagicMock(id="schema_id")
    )
    mock_acapy_client.server.get_config.return_value = AdminConfig(
        config={"wallet.type": "askar"}
    )

    did, schema_id = await get_did_and_schema_id_from_cred_def_attachment(
        mock_acapy_client,
        {"identifier": "identifier_value", "operation": {"ref": "ref_value"}},
    )

    assert did == "did:sov:identifier_value"
    assert schema_id == "schema_id"
    mock_acapy_client.schema.get_schema.assert_awaited_once_with(schema_id="ref_value")


@pytest.mark.anyio
async def test_is_credential_definition_transaction_fail_no_identifier():
    assert (
        is_credential_definition_transaction(
            operation_type=TransactionTypes.CLAIM_DEF,
            attachment={
                "not_identifier": "identifier_value",
                "operation": {"ref": "ref_value"},
            },
        )
        is False
    )


@pytest.mark.anyio
async def test_is_credential_definition_transaction_fail_no_ref():
    assert (
        is_credential_definition_transaction(
            operation_type=TransactionTypes.CLAIM_DEF,
            attachment={
                "identifier": "identifier_value",
                "operation": {"no_ref": "ref_value"},
            },
        )
        is False
    )


@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
@pytest.mark.anyio
async def test_get_did_and_schema_id_from_cred_def_attachment_fail_no_var_schema_id(
    mock_acapy_client,
    wallet_type,
):
    if wallet_type == "askar":
        mock_acapy_client.schema.get_schema.return_value = MagicMock(
            var_schema=MagicMock(id=None)
        )
    else:
        mock_acapy_client.anoncreds_schemas.get_schema.return_value = MagicMock(
            schema_id=None
        )

    # Patch the EndorserConfig singleton
    with patch.object(
        EndorserConfig, "wallet_type", new_callable=Mock(return_value=wallet_type)
    ):
        with pytest.raises(ValueError) as exc:
            await get_did_and_schema_id_from_cred_def_attachment(
                mock_acapy_client,
                {"identifier": "identifier_value", "operation": {"ref": "ref_value"}},
            )

        assert "Could not extract schema id from schema response" in str(exc.value)

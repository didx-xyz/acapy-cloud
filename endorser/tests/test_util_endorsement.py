import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from endorser.util.endorsement import accept_endorsement, should_accept_endorsement
from shared.models.endorsement import Endorsement

valid_endorsement = Endorsement(
    state="request-received", transaction_id="test-transaction"
)


@pytest.mark.anyio
async def test_should_accept_endorsement_success_claim_def(mock_acapy_client, mocker):
    # Mock the dependency functions
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "102"},
        },
    )
    mocker.patch(
        "endorser.util.endorsement.get_did_and_schema_id_from_cred_def_attachment",
        return_value=("did:sov:test-did", "test-schema-id"),
    )
    mocker.patch("endorser.util.endorsement.is_valid_issuer", return_value=True)

    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is True


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_not_claim_def(mock_acapy_client, mocker):
    # Mock the dependency functions
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "99"},
        },
    )
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_no_attach(mock_acapy_client, mocker):
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    # Assume the transaction has no attachments
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value=None,
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_no_operation(mock_acapy_client, mocker):
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    # Assume the transaction has no operation field
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={"something": "else"},
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_no_type(mock_acapy_client, mocker):
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    # Assume the transaction has no type field
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={"operation": {"no": "type"}},
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_is_cred_def(mock_acapy_client, mocker):
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "113"},  # 113 for cred def
        },
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is True


@pytest.mark.anyio
async def test_should_accept_endorsement_is_attrib(mock_acapy_client, mocker):
    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "100"},  # 100 for attrib
        },
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is True


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_not_cred_def(mock_acapy_client, mocker):
    # Assume the transaction has valid attachments
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "99"},
        },
    )

    # Assume the transaction is not for a credential definition
    mocker.patch(
        "endorser.util.endorsement.is_credential_definition_transaction",
        return_value=False,
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_not_correct_attach(
    mock_acapy_client, mocker
):
    # Assume the transaction has valid attachments
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"x": "test-ref"},
        },
    )

    # Assume the transaction is not for a credential definition
    mocker.patch(
        "endorser.util.endorsement.is_credential_definition_transaction",
        return_value=True,
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_not_valid_issuer(
    mock_acapy_client, mocker
):
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "102"},
        },
    )
    mocker.patch(
        "endorser.util.endorsement.get_did_and_schema_id_from_cred_def_attachment",
        return_value=("did:sov:test-did", "test-schema-id"),
    )
    mocker.patch("endorser.util.endorsement.is_valid_issuer", return_value=False)

    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_should_accept_endorsement_retries_on_http_exception(
    mock_acapy_client, mocker
):
    # Mock valid flow
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "102"},
        },
    )
    mocker.patch(
        "endorser.util.endorsement.is_credential_definition_transaction",
        return_value=True,
    )
    mocker.patch(
        "endorser.util.endorsement.get_did_and_schema_id_from_cred_def_attachment",
        return_value=("did:sov:test-did", "test-schema-id"),
    )

    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    # Mock is_valid_issuer function behaviour - first exception, then True
    mock_is_valid_issuer = mocker.patch(
        "endorser.util.endorsement.is_valid_issuer",
        side_effect=[HTTPException(status_code=500), True],
    )

    # Mock retry_is_valid_issuer to use a shorter retry delay
    async def mock_retry_is_valid_issuer(
        did, schema_id, _, max_retries=5, retry_delay=0.01
    ):
        for attempt in range(max_retries):
            try:
                valid_issuer = await mock_is_valid_issuer(did, schema_id)
                if valid_issuer:
                    return True
                return False
            except HTTPException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    return False

    mocker.patch(
        "endorser.util.endorsement.retry_is_valid_issuer",
        side_effect=mock_retry_is_valid_issuer,
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    # Assertions
    assert (
        result
    ), "The endorsement should be accepted due to is_valid_issuer true after retry."
    assert (
        mock_is_valid_issuer.call_count == 2
    ), "is_valid_issuer should have been called exactly twice."


@pytest.mark.anyio
async def test_should_accept_endorsement_fails_after_max_retries(
    mock_acapy_client, mocker
):
    # Mock valid flow
    mocker.patch(
        "endorser.util.endorsement.get_endorsement_request_attachment",
        return_value={
            "identifier": "test-identifier",
            "operation": {"ref": "test-ref", "type": "102"},
        },
    )
    mocker.patch(
        "endorser.util.endorsement.is_credential_definition_transaction",
        return_value=True,
    )
    mocker.patch(
        "endorser.util.endorsement.get_did_and_schema_id_from_cred_def_attachment",
        return_value=("did:sov:test-did", "test-schema-id"),
    )

    # Mock transaction response
    transaction_mock = MagicMock()
    transaction_mock.state = "request_received"
    mock_acapy_client.endorse_transaction.get_transaction.return_value = (
        transaction_mock
    )

    # Mock is_valid_issuer function behaviour - always exception
    mock_is_valid_issuer = mocker.patch(
        "endorser.util.endorsement.is_valid_issuer",
        side_effect=HTTPException(status_code=500),
    )

    # Mock retry_is_valid_issuer to use a shorter retry delay
    async def mock_retry_is_valid_issuer(
        did, schema_id, _, max_retries=5, retry_delay=0.01
    ):
        for attempt in range(max_retries):
            try:
                valid_issuer = await mock_is_valid_issuer(did, schema_id)
                if valid_issuer:
                    return True
                return False
            except HTTPException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    return False

    mocker.patch(
        "endorser.util.endorsement.retry_is_valid_issuer",
        side_effect=mock_retry_is_valid_issuer,
    )

    result = await should_accept_endorsement(mock_acapy_client, valid_endorsement)

    # Assertions
    assert (
        result is False
    ), "The endorsement should not be accepted due to is_valid_issuer failing repeatedly"
    assert (
        mock_is_valid_issuer.call_count == 5
    ), "is_valid_issuer should have been called exactly `max_retries` times."


@pytest.mark.anyio
async def test_should_accept_endorsement_fail_bad_state(mock_acapy_client):
    invalid_endorsement = Endorsement(
        state="transaction-created", transaction_id="test-transaction"
    )

    result = await should_accept_endorsement(mock_acapy_client, invalid_endorsement)

    assert result is False


@pytest.mark.anyio
async def test_accept_endorsement(mock_acapy_client):
    await accept_endorsement(mock_acapy_client, valid_endorsement)

    mock_acapy_client.endorse_transaction.endorse_transaction.assert_awaited_once_with(
        tran_id=valid_endorsement.transaction_id
    )

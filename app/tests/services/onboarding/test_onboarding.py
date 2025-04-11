from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    DID,
    AcaPyClient,
    ConnectionList,
    ConnRecord,
    InvitationCreateRequest,
    InvitationMessage,
    InvitationRecord,
    TransactionList,
    TransactionRecord,
)

from app.exceptions import CloudApiException
from app.services.onboarding import issuer, verifier
from shared.util.mock_agent_controller import get_mock_agent_controller

did_object = DID(
    did="WgWxqztrNooG92RXvxSTWv",
    verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
    posture="wallet_only",
    key_type="ed25519",
    method="sov",
)


@pytest.mark.anyio
async def test_onboard_issuer_public_did_exists(
    mock_agent_controller: AcaPyClient,
):

    endorser_controller = get_mock_agent_controller()

    endorser_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage()
    )
    mock_agent_controller.out_of_band.receive_invitation.return_value = ConnRecord(
        connection_id="abc"
    )

    mock_agent_controller.endorse_transaction.set_endorser_role.return_value = None
    endorser_controller.endorse_transaction.set_endorser_role.return_value = None
    mock_agent_controller.endorse_transaction.set_endorser_info.return_value = None

    invitation_url = "https://invitation.com/"

    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation_url=invitation_url,
    )
    with patch(
        "app.services.acapy_wallet.get_public_did",
        return_value=did_object,
    ):
        onboard_result = await issuer.onboard_issuer(
            issuer_label="issuer_name",
            endorser_controller=endorser_controller,
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
        )

    assert onboard_result.did == "did:sov:WgWxqztrNooG92RXvxSTWv"


@pytest.mark.anyio
async def test_onboard_issuer_no_public_did(
    mock_agent_controller: AcaPyClient,
):
    issuer_connection_id = "abc"
    endorser_connection_id = "xyz"

    endorser_controller = get_mock_agent_controller()

    # Mock the necessary functions and methods
    endorser_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage()
    )
    mock_agent_controller.out_of_band.receive_invitation.return_value = ConnRecord(
        connection_id=issuer_connection_id
    )
    endorser_controller.connection.get_connections.return_value = ConnectionList(
        results=[
            ConnRecord(connection_id=endorser_connection_id, rfc23_state="completed")
        ]
    )
    mock_agent_controller.endorse_transaction.set_endorser_role.return_value = None
    endorser_controller.endorse_transaction.set_endorser_role.return_value = None
    mock_agent_controller.endorse_transaction.set_endorser_info.return_value = None
    mock_agent_controller.endorse_transaction.get_records.return_value = (
        TransactionList(
            results=[
                TransactionRecord(
                    connection_id=issuer_connection_id, state="transaction_acked"
                )
            ]
        )
    )

    # Create an invitation as well
    invitation_url = "https://invitation.com/"
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation_url=invitation_url,
    )

    # Patch asyncio.sleep to return immediately
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=[
            CloudApiException(detail="Not found"),  # Issuer did doesn't exist yet
            did_object,  # Endorser did
        ],
    ), patch(
        "app.services.acapy_wallet.create_did", return_value=did_object
    ) as acapy_wallet_create_did_mock, patch(
        "app.services.acapy_ledger.register_nym_on_ledger", return_value=None
    ) as acapy_ledger_register_nym_on_ledger_mock, patch(
        "app.services.acapy_ledger.accept_taa_if_required", return_value=None
    ) as acapy_ledger_accept_taa_if_required_mock, patch(
        "app.services.acapy_wallet.set_public_did", return_value=None
    ) as acapy_wallet_set_public_did_mock:
        onboard_result = await issuer.onboard_issuer(
            issuer_label="issuer_name",
            endorser_controller=endorser_controller,
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
        )

    # Assertions
    assert onboard_result.did == "did:sov:WgWxqztrNooG92RXvxSTWv"
    acapy_ledger_accept_taa_if_required_mock.assert_called_once_with(
        mock_agent_controller
    )
    acapy_wallet_create_did_mock.assert_called_once_with(mock_agent_controller)
    acapy_ledger_register_nym_on_ledger_mock.assert_called_once_with(
        mock_agent_controller,
        did="WgWxqztrNooG92RXvxSTWv",
        verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
        alias="issuer_name",
        create_transaction_for_endorser=True,
    )
    acapy_wallet_set_public_did_mock.assert_called_once_with(
        mock_agent_controller,
        did="WgWxqztrNooG92RXvxSTWv",
        create_transaction_for_endorser=True,
    )
    mock_sleep.assert_awaited()  # Ensure that sleep was called and patched


@pytest.mark.anyio
async def test_onboard_issuer_no_public_did_endorser_did_exception(
    mock_agent_controller: AcaPyClient,
):
    endorser_controller = get_mock_agent_controller()

    with patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=CloudApiException(detail="Error"),
    ), pytest.raises(CloudApiException, match="Unable to get endorser public DID."):
        await issuer.onboard_issuer(
            issuer_label="issuer_name",
            endorser_controller=endorser_controller,
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
        )


@pytest.mark.anyio
async def test_onboard_issuer_no_public_did_connection_error(
    mock_agent_controller: AcaPyClient,
):
    endorser_controller = get_mock_agent_controller()

    mock_agent_controller.out_of_band.receive_invitation.side_effect = (
        CloudApiException(detail="Error")
    )

    with patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=[CloudApiException(detail="Error"), did_object],
    ), pytest.raises(
        CloudApiException, match="Error creating connection with endorser"
    ):
        await issuer.onboard_issuer(
            issuer_label="issuer_name",
            endorser_controller=endorser_controller,
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
        )


@pytest.mark.anyio
async def test_onboard_verifier_public_did_exists(mock_agent_controller: AcaPyClient):
    with patch(
        "app.services.acapy_wallet.get_public_did",
        return_value=did_object,
    ) as acapy_wallet_get_public_did_mock:
        onboard_result = await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )

    assert onboard_result.did == "did:sov:WgWxqztrNooG92RXvxSTWv"
    acapy_wallet_get_public_did_mock.assert_called_once_with(
        controller=mock_agent_controller
    )


@pytest.mark.anyio
async def test_onboard_verifier_no_public_did(mock_agent_controller: AcaPyClient):

    did_key = "did:key:123#456"
    invitation_url = "https://invitation.com/"

    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation_url=invitation_url,
        invitation=InvitationMessage(services=[{"recipientKeys": [did_key]}]),
    )

    with patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=CloudApiException(detail="No public did found"),
    ):
        onboard_result = await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )

    assert onboard_result.did == "did:key:123"
    assert str(onboard_result.didcomm_invitation) == invitation_url
    mock_agent_controller.out_of_band.create_invitation.assert_called_once_with(
        auto_accept=True,
        multi_use=True,
        body=InvitationCreateRequest(
            use_public_did=False,
            alias="Trust Registry verifier_name",
            handshake_protocols=["https://didcomm.org/didexchange/1.0"],
        ),
    )


@pytest.mark.anyio
async def test_onboard_verifier_no_recipient_keys(mock_agent_controller: AcaPyClient):
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage(services=[{"recipientKeys": []}]),
    )

    with patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=CloudApiException(detail="No public did found"),
    ), pytest.raises(CloudApiException):
        await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )


@pytest.mark.anyio
async def test_onboard_verifier_invalid_invitation(mock_agent_controller: AcaPyClient):
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage(services=[]),
    )

    with patch(
        "app.services.acapy_wallet.get_public_did",
        side_effect=CloudApiException(detail="No public did found"),
    ), pytest.raises(CloudApiException):
        await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )

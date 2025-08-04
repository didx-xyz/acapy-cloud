from unittest.mock import patch

import pytest
from aries_cloudcontroller import (
    DID,
    AcaPyClient,
    ConnRecord,
    InvitationCreateRequest,
    InvitationMessage,
    InvitationRecord,
)

from app.exceptions import CloudApiException
from app.models.wallet import DIDCreate
from app.services.onboarding import issuer, verifier

did_object = DID(
    did="did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6",
    verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
    posture="posted",
    key_type="ed25519",
    method="cheqd",
)


@pytest.mark.anyio
async def test_onboard_issuer_public_did_exists(
    mock_agent_controller: AcaPyClient,
):
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
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
        )

    assert (
        onboard_result.did == "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6"
    )


@pytest.mark.anyio
async def test_onboard_issuer_no_public_did(
    mock_agent_controller: AcaPyClient,
):
    issuer_connection_id = "abc"

    # Mock the necessary functions and methods
    mock_agent_controller.out_of_band.receive_invitation.return_value = ConnRecord(
        connection_id=issuer_connection_id
    )

    # Create an invitation as well
    invitation_url = "https://invitation.com/"
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation_url=invitation_url,
    )

    # Patch asyncio.sleep to return immediately
    with (
        patch(
            "app.services.acapy_wallet.get_public_did",
            side_effect=[
                CloudApiException(detail="Not found"),  # Issuer did doesn't exist yet
                did_object,  # Endorser did
            ],
        ),
        patch(
            "app.services.acapy_wallet.create_did", return_value=did_object
        ) as acapy_wallet_create_did_mock,
    ):
        onboard_result = await issuer.onboard_issuer(
            issuer_controller=mock_agent_controller,
            issuer_wallet_id="issuer_wallet_id",
            issuer_label="issuer_name",
        )

    # Assertions
    assert (
        onboard_result.did == "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6"
    )  # TODO: cheqd
    acapy_wallet_create_did_mock.assert_called_once_with(
        mock_agent_controller, did_create=DIDCreate(method="cheqd", network="testnet")
    )


@pytest.mark.anyio
async def test_onboard_verifier_public_did_exists(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.acapy_wallet.get_public_did",
        return_value=did_object,
    ) as acapy_wallet_get_public_did_mock:
        onboard_result = await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )

    assert (
        onboard_result.did == "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6"
    )
    acapy_wallet_get_public_did_mock.assert_called_once_with(
        controller=mock_agent_controller
    )


@pytest.mark.anyio
async def test_onboard_verifier_no_public_did(
    mock_agent_controller: AcaPyClient,
):
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
            handshake_protocols=["https://didcomm.org/didexchange/1.1"],
        ),
    )


@pytest.mark.anyio
async def test_onboard_verifier_no_recipient_keys(
    mock_agent_controller: AcaPyClient,
):
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage(services=[{"recipientKeys": []}]),
    )

    with (
        patch(
            "app.services.acapy_wallet.get_public_did",
            side_effect=CloudApiException(detail="No public did found"),
        ),
        pytest.raises(CloudApiException),
    ):
        await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )


@pytest.mark.anyio
async def test_onboard_verifier_invalid_invitation(
    mock_agent_controller: AcaPyClient,
):
    mock_agent_controller.out_of_band.create_invitation.return_value = InvitationRecord(
        invitation=InvitationMessage(services=[]),
    )

    with (
        patch(
            "app.services.acapy_wallet.get_public_did",
            side_effect=CloudApiException(detail="No public did found"),
        ),
        pytest.raises(CloudApiException),
    ):
        await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )

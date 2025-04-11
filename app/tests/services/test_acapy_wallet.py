import pytest
from aries_cloudcontroller import DID, AcaPyClient, DIDResult

from app.exceptions import CloudApiException
from app.services import acapy_wallet


@pytest.mark.anyio
async def test_assert_public_did(mock_agent_controller: AcaPyClient):
    did = DID(
        did="Ehx3RZSV38pn3MYvxtHhbQ",
        verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
        posture="wallet_only",
        key_type="ed25519",
        method="sov",
    )
    mock_agent_controller.wallet.get_public_did.return_value = DIDResult(result=did)

    did = await acapy_wallet.assert_public_did(mock_agent_controller)
    assert did == "did:sov:Ehx3RZSV38pn3MYvxtHhbQ"

    with pytest.raises(CloudApiException, match="Agent has no public did"):
        mock_agent_controller.wallet.get_public_did.return_value = DIDResult(
            result=None
        )
        await acapy_wallet.assert_public_did(mock_agent_controller)


@pytest.mark.anyio
async def test_error_on_get_pub_did(mock_agent_controller: AcaPyClient):
    mock_agent_controller.wallet.get_public_did.return_value = DIDResult(result=None)

    with pytest.raises(CloudApiException) as exc:
        await acapy_wallet.get_public_did(mock_agent_controller)
    assert exc.value.status_code == 404
    assert "No public did found" in exc.value.detail


@pytest.mark.anyio
async def test_error_on_assign_pub_did(mock_agent_controller: AcaPyClient):
    mock_agent_controller.wallet.set_public_did.return_value = DIDResult(result=None)

    with pytest.raises(CloudApiException) as exc:
        await acapy_wallet.set_public_did(mock_agent_controller, did="did")
    assert exc.value.status_code == 400
    assert "Error setting public did" in exc.value.detail

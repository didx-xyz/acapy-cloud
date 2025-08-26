import uuid

import pytest
from aries_cloudcontroller import (
    DID,
    AcaPyClient,
    CreateCheqdDIDRequest,
    CreateCheqdDIDResponse,
    DIDResult,
)

from app.exceptions import CloudApiException
from app.models.wallet import DIDCreate
from app.services import acapy_wallet

did_cheqd = f"did:cheqd:testnet:{uuid.uuid4()}"


@pytest.mark.anyio
async def test_assert_public_did(mock_agent_controller: AcaPyClient):
    did_object = DID(
        did=did_cheqd,
        verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
        posture="posted",
        key_type="ed25519",
        method="cheqd",
    )
    mock_agent_controller.wallet.get_public_did.return_value = DIDResult(
        result=did_object
    )

    did = await acapy_wallet.assert_public_did(mock_agent_controller)
    assert did == did_cheqd

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


@pytest.mark.anyio
async def test_create_cheqd_did_success(mock_agent_controller: AcaPyClient):
    did_create_request = DIDCreate(
        method="cheqd",
        seed="testseed000000000000000000000001",
    )

    expected_verkey = "WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv"

    mock_agent_controller.did.did_cheqd_create_post.return_value = (
        CreateCheqdDIDResponse(
            did=did_cheqd,
            verkey=expected_verkey,
        )
    )

    created_did = await acapy_wallet.create_did(
        mock_agent_controller, did_create=did_create_request
    )

    assert created_did.did == did_cheqd
    assert created_did.verkey == expected_verkey
    assert created_did.method == "cheqd"
    assert created_did.key_type == "ed25519"  # Default key_type for cheqd
    assert created_did.posture == "posted"  # Default posture for cheqd

    mock_agent_controller.did.did_cheqd_create_post.assert_called_once()
    call_args = mock_agent_controller.did.did_cheqd_create_post.call_args
    assert call_args is not None
    assert isinstance(call_args.kwargs["body"], CreateCheqdDIDRequest)
    assert (
        call_args.kwargs["body"].options["seed"] == "testseed000000000000000000000001"
    )


@pytest.mark.anyio
async def test_create_cheqd_did_success_no_seed(
    mock_agent_controller: AcaPyClient,
):
    did_create_request = DIDCreate(method="cheqd")

    expected_verkey = "HkPgtEv9hrGjGkVSkL4sT8HkPgtEv9hrGjGkVSkL4sT8"

    mock_agent_controller.did.did_cheqd_create_post.return_value = (
        CreateCheqdDIDResponse(
            did=did_cheqd,
            verkey=expected_verkey,
        )
    )

    created_did = await acapy_wallet.create_did(
        mock_agent_controller, did_create=did_create_request
    )

    assert created_did.did == did_cheqd
    assert created_did.verkey == expected_verkey
    assert created_did.method == "cheqd"

    mock_agent_controller.did.did_cheqd_create_post.assert_called_once()
    call_args = mock_agent_controller.did.did_cheqd_create_post.call_args
    assert call_args is not None
    assert isinstance(call_args.kwargs["body"], CreateCheqdDIDRequest)
    assert (
        "seed" not in call_args.kwargs["body"].options
    )  # Ensure seed is not passed if not provided


@pytest.mark.anyio
async def test_create_cheqd_did_fail_missing_did(
    mock_agent_controller: AcaPyClient,
):
    did_create_request = DIDCreate(method="cheqd", options={"network": "testnet"})

    mock_agent_controller.did.did_cheqd_create_post.return_value = (
        CreateCheqdDIDResponse(verkey="some_verkey")  # Missing did
    )

    with pytest.raises(CloudApiException, match="Error creating cheqd did."):
        await acapy_wallet.create_did(
            mock_agent_controller, did_create=did_create_request
        )


@pytest.mark.anyio
async def test_create_cheqd_did_fail_missing_verkey(
    mock_agent_controller: AcaPyClient,
):
    did_create_request = DIDCreate(method="cheqd", options={"network": "testnet"})

    mock_agent_controller.did.did_cheqd_create_post.return_value = (
        CreateCheqdDIDResponse(did="some_did")  # Missing verkey
    )

    with pytest.raises(CloudApiException, match="Error creating cheqd did."):
        await acapy_wallet.create_did(
            mock_agent_controller, did_create=did_create_request
        )

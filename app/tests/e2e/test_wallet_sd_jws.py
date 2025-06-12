import pytest
from aries_cloudcontroller import DIDCreate
from fastapi import HTTPException

from app.models.sd_jws import SDJWSCreateRequest
from shared.exceptions import CloudApiValueError
from shared.util.rich_async_client import RichAsyncClient


@pytest.mark.anyio
async def test_sign_sdjws_success(alice_member_client: RichAsyncClient):
    # Create DID:key for Alice
    did_info = await alice_member_client.post(
        "v1/wallet/dids", json=DIDCreate(method="key").model_dump()
    )
    did = did_info.json()["did"]

    request_payload = SDJWSCreateRequest(
        did=did,
        headers={},
        payload={"example": "payload"},
        verification_method=None,
    )

    response = await alice_member_client.post(
        "/v1/wallet/sd-jws/sign", json=request_payload.model_dump()
    )

    assert response.status_code == 200
    assert "sd_jws" in response.json()


@pytest.mark.anyio
async def test_sign_sdjws_x(alice_member_client: RichAsyncClient):
    with pytest.raises(CloudApiValueError):
        # Requires at least one of did or verification method
        SDJWSCreateRequest(
            did=None,
            headers={},
            payload={"example": "payload"},
            verification_method=None,
        )

    with pytest.raises(HTTPException) as exc_info:
        await alice_member_client.post("/v1/wallet/sd-jws/sign", json={})
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        # If did / verification method are bad values
        request = SDJWSCreateRequest(
            did="bad did",
            headers={},
            payload={"example": "payload"},
            verification_method="bad method",
        ).model_dump()
        await alice_member_client.post("/v1/wallet/sd-jws/sign", json=request)
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_sign_and_verify_sdjws_success(
    alice_member_client: RichAsyncClient,
):
    # Create DID:key for Alice
    did_info = await alice_member_client.post(
        "v1/wallet/dids", json=DIDCreate(method="key").model_dump()
    )
    did = did_info.json()["did"]

    request_payload = SDJWSCreateRequest(
        did=did,
        headers={},
        payload={"example": "payload"},
        verification_method=None,
    )

    sign_response = await alice_member_client.post(
        "/v1/wallet/sd-jws/sign", json=request_payload.model_dump()
    )

    assert sign_response.status_code == 200

    verify_response = await alice_member_client.post(
        "/v1/wallet/sd-jws/verify", json=sign_response.json()
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True


@pytest.mark.anyio
async def test_verify_sdjws_x(alice_member_client: RichAsyncClient):
    with pytest.raises(HTTPException) as exc_info:
        await alice_member_client.post(
            "/v1/wallet/sd-jws/verify", json={"sd_jws": "bad value"}
        )
    assert exc_info.value.status_code == 422

import os
from typing import List

import pytest
from aries_cloudcontroller import DID, AcaPyClient
from assertpy import assert_that

import app.services.acapy_wallet as wallet_service
from app.dependencies.auth import AcaPyAuthVerified
from app.models.wallet import SetDidEndpointRequest
from app.routes.wallet.dids import (
    get_did_endpoint,
    get_public_did,
    list_dids,
    router,
    set_did_endpoint,
)
from app.tests.util.ledger import create_public_did, post_to_ledger
from shared import RichAsyncClient

WALLET_BASE_PATH = router.prefix

# The setting public did test should be skipped in prod.
# SKIP_SET_PUBLIC_DID env var is configured in capi_test charts
skip_set_public_did = os.getenv("SKIP_SET_PUBLIC_DID") is not None


async def create_did_mock(governance_client: RichAsyncClient):
    did_response = await governance_client.post(WALLET_BASE_PATH)
    did_response = did_response.json()
    did = did_response["did"]
    return did


@pytest.mark.anyio
async def test_list_dids(
    governance_client: RichAsyncClient, mock_governance_auth: AcaPyAuthVerified
):
    response = await governance_client.get(WALLET_BASE_PATH)

    assert response.status_code == 200
    response = response.json()

    res_method: List[DID] = await list_dids(auth=mock_governance_auth)
    res_method_dict = list(map(lambda x: x.to_dict(), res_method))
    assert res_method_dict == response


@pytest.mark.anyio
async def test_create_local_did(governance_client: RichAsyncClient):
    response = await governance_client.post(WALLET_BASE_PATH)

    assert_that(response.status_code).is_equal_to(200)
    response = response.json()

    assert_that(response).contains("did", "verkey")


@pytest.mark.anyio
async def test_get_public_did(
    governance_client: RichAsyncClient, mock_governance_auth: AcaPyAuthVerified
):
    response = await governance_client.get(f"{WALLET_BASE_PATH}/public")

    assert_that(response.status_code).is_equal_to(200)
    response = response.json()

    assert_that(response).contains("did", "verkey")

    res_method: DID = await get_public_did(auth=mock_governance_auth)
    assert res_method.to_dict() == response


@pytest.mark.anyio
async def test_get_did_endpoint(governance_client: RichAsyncClient):
    did = await create_did_mock(governance_client)
    response = await governance_client.get(f"{WALLET_BASE_PATH}/{did}/endpoint")
    assert_that(response.status_code).is_equal_to(200)

    response = response.json()
    assert response["did"] == did


@pytest.mark.skipif(
    skip_set_public_did,
    reason="Avoid creating additional did for governance from different seed",
)
@pytest.mark.anyio
async def test_set_public_did(
    governance_client: RichAsyncClient, governance_acapy_client: AcaPyClient
):
    did_object = await wallet_service.create_did(governance_acapy_client)
    await post_to_ledger(did=did_object.did, verkey=did_object.verkey)

    did = did_object.did
    response = await governance_client.put(f"{WALLET_BASE_PATH}/public?did={did}")

    assert_that(response.status_code).is_equal_to(200)

    # With endorsement the set pub dic returns None but sets the did correctly
    # So let's get it a different way and check that it is correct
    response = await governance_client.get(f"{WALLET_BASE_PATH}/public")
    assert_that(response.status_code).is_equal_to(200)
    response = response.json()

    assert_that(response).contains("did", "verkey")
    assert_that(response).has_did(did)


@pytest.mark.anyio
async def test_set_did_endpoint(
    governance_acapy_client: AcaPyClient, mock_governance_auth: AcaPyAuthVerified
):
    # Don't want us overwriting the real endpoint, so not setting as public did
    did = await create_public_did(governance_acapy_client, set_public=False)
    endpoint = "https://ssi.com"

    await set_did_endpoint(
        did.did,
        SetDidEndpointRequest(endpoint=endpoint),
        auth=mock_governance_auth,
    )

    retrieved_endpoint = await get_did_endpoint(did.did, auth=mock_governance_auth)

    assert_that(endpoint).is_equal_to(retrieved_endpoint.endpoint)

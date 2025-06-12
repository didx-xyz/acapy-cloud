import os

import pytest
from aries_cloudcontroller import DID

from app.dependencies.auth import AcaPyAuthVerified
from app.routes.wallet.dids import get_public_did, list_dids, router
from shared import RichAsyncClient

# Tests can conflict if they run in parallel, e.g. test_set_did_endpoint during test_list_dids changes expected response
pytestmark = pytest.mark.xdist_group(name="sequential_test_group")

WALLET_BASE_PATH = router.prefix

# The setting public did test should be skipped in prod.
# SKIP_SET_PUBLIC_DID env var is configured in capi_test charts
skip_set_public_did = os.getenv("SKIP_SET_PUBLIC_DID") is not None


async def create_did_mock(governance_client: RichAsyncClient) -> str:
    did_response = await governance_client.post(WALLET_BASE_PATH)
    did_response = did_response.json()
    did = did_response["did"]
    return did


@pytest.mark.anyio
async def test_list_dids(
    governance_client: RichAsyncClient, mock_governance_auth: AcaPyAuthVerified
) -> None:
    # Capture the existing DIDs before the request
    initial_dids = await list_dids(auth=mock_governance_auth)
    initial_dids_set = {x.did for x in initial_dids}

    # Make the GET request
    response = await governance_client.get(WALLET_BASE_PATH)
    assert response.status_code == 200
    response_data = response.json()

    # Filter the response to include only the initial DIDs
    filtered_response_data = [
        did_dict for did_dict in response_data if did_dict["did"] in initial_dids_set
    ]

    # Compare the filtered response with the initial DIDs
    initial_dids_dict = [x.to_dict() for x in initial_dids]
    assert filtered_response_data == initial_dids_dict


@pytest.mark.anyio
async def test_create_local_did(governance_client: RichAsyncClient) -> None:
    response = await governance_client.post(WALLET_BASE_PATH)

    assert response.status_code == 200
    response = response.json()

    assert response["did"]
    assert response["verkey"]


@pytest.mark.anyio
async def test_get_public_did(
    governance_client: RichAsyncClient, mock_governance_auth: AcaPyAuthVerified
) -> None:
    response = await governance_client.get(f"{WALLET_BASE_PATH}/public")

    assert response.status_code == 200
    response = response.json()

    assert response["did"]
    assert response["verkey"]

    res_method: DID = await get_public_did(auth=mock_governance_auth)
    assert res_method.to_dict() == response


@pytest.mark.anyio
async def test_get_did_endpoint(governance_client: RichAsyncClient) -> None:
    did = await create_did_mock(governance_client)
    response = await governance_client.get(f"{WALLET_BASE_PATH}/{did}/endpoint")
    assert response.status_code == 200

    response = response.json()
    assert response["did"] == did

import pytest
from fastapi import HTTPException

from app.routes.wallet.credentials import router
from app.tests.util.regression_testing import TestMode
from shared import RichAsyncClient
from shared.models.credential_exchange import CredentialExchange

WALLET_CREDENTIALS_PATH = router.prefix


@pytest.mark.anyio
async def test_get_credentials(alice_member_client: RichAsyncClient):
    # Assert empty list is returned for empty wallet when fetching all credentials
    response = await alice_member_client.get(WALLET_CREDENTIALS_PATH)
    assert response.status_code == 200


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Don't delete credentials in regression run",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_and_delete_credential_record(
    alice_member_client: RichAsyncClient,
    issue_anoncreds_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
):
    credentials_response = await alice_member_client.get(WALLET_CREDENTIALS_PATH)

    assert credentials_response.status_code == 200
    credentials_response = credentials_response.json()["results"]

    credential_id = credentials_response[0]["credential_id"]
    # While in the broader context of Aries and credentials, referent can refer to specific attributes,
    # when dealing with the wallet's stored credentials, the referent becomes synonymous with a credential_id
    # specific to the wallet. It's how the wallet references and retrieves that particular credential record.

    fetch_response = await alice_member_client.get(
        f"{WALLET_CREDENTIALS_PATH}/{credential_id}"
    )
    assert fetch_response.status_code == 200

    # Assert we can delete this credential
    delete_response = await alice_member_client.delete(
        f"{WALLET_CREDENTIALS_PATH}/{credential_id}"
    )
    assert delete_response.status_code == 204

    # Assert referent is no longer in credentials list
    credentials_response = (
        await alice_member_client.get(WALLET_CREDENTIALS_PATH)
    ).json()["results"]
    for cred in credentials_response:
        assert cred["credential_id"] != credential_id

    # Assert fetching deleted credential yields 404
    with pytest.raises(HTTPException) as exc:
        await alice_member_client.get(f"{WALLET_CREDENTIALS_PATH}/{credential_id}")
    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Skipping due to regression run",
)
@pytest.mark.parametrize(
    "issue_alice_many_anoncreds", [3], indirect=True
)  # issue alice 3 creds
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_credential_record_with_limit(
    alice_member_client: RichAsyncClient,
    issue_alice_many_anoncreds,  # pylint: disable=unused-argument
):
    valid_params = [
        {"limit": 1},
        {"limit": 2},
        {"limit": 3},
        {"limit": 4},
        {"limit": 1, "offset": 4},
        {"limit": 2, "offset": 2},
    ]

    expected_length = [1, 2, 3, 3, 0, 1]

    for params, length in zip(valid_params, expected_length):
        response = (
            await alice_member_client.get(WALLET_CREDENTIALS_PATH, params=params)
        ).json()
        assert len(response["results"]) == length

    invalid_params = [
        {"limit": -1},  # must be positive
        {"offset": -1},  # must be positive
        {"limit": 0},  # must be greater than 0
        {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
    ]

    for params in invalid_params:
        with pytest.raises(HTTPException) as exc:
            await alice_member_client.get(WALLET_CREDENTIALS_PATH, params=params)
        assert exc.value.status_code == 422

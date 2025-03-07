import pytest
from aries_cloudcontroller import AcaPyClient
from assertpy import assert_that
from fastapi import HTTPException

from app.models.definitions import CredentialSchema
from app.models.tenants import CreateTenantResponse
from app.routes.trust_registry import router
from shared.util.rich_async_client import RichAsyncClient

CLOUDAPI_TRUST_REGISTRY_PATH = router.prefix


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_schemas(
    indy_schema_definition: CredentialSchema,  # pylint: disable=unused-argument
    indy_schema_definition_alt: CredentialSchema,  # pylint: disable=unused-argument
    trust_registry_client: RichAsyncClient,
):
    schemas_response = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/schemas"
    )

    assert schemas_response.status_code == 200
    schemas = schemas_response.json()
    assert len(schemas) >= 2


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_schema_by_id(
    indy_schema_definition: CredentialSchema, trust_registry_client: RichAsyncClient
):
    schema_response = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/schemas/{indy_schema_definition.id}"
    )

    assert schema_response.status_code == 200
    schema = schema_response.json()
    assert_that(schema).contains("did", "name", "version", "id")

    with pytest.raises(HTTPException) as exc:
        await trust_registry_client.get(
            f"{CLOUDAPI_TRUST_REGISTRY_PATH}/schemas/bad_schema_id"
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_actors(
    faber_indy_issuer: CreateTenantResponse,
    faber_indy_acapy_client: AcaPyClient,
    trust_registry_client: RichAsyncClient,
):
    all_actors = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors"
    )
    assert all_actors.status_code == 200
    actors = all_actors.json()
    assert_that(actors[0]).contains("id", "name", "roles", "did", "didcomm_invitation")

    actors_by_id = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_id={faber_indy_issuer.wallet_id}"
    )
    assert actors_by_id.status_code == 200
    actor = actors_by_id.json()[0]

    actor_did = actor["did"]
    did_result = await faber_indy_acapy_client.wallet.get_public_did()
    assert actor_did == f"did:sov:{did_result.result.did}"

    actor_name = actor["name"]
    assert actor_name == faber_indy_issuer.wallet_label
    assert_that(actor).contains("id", "name", "roles", "did", "didcomm_invitation")

    actors_by_did = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_did={actor_did}"
    )
    assert actors_by_did.status_code == 200
    assert_that(actors_by_did.json()[0]).contains(
        "id", "name", "roles", "did", "didcomm_invitation"
    )

    actors_by_name = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_name={faber_indy_issuer.wallet_label}"
    )
    assert actors_by_name.status_code == 200
    assert_that(actors_by_name.json()[0]).contains(
        "id", "name", "roles", "did", "didcomm_invitation"
    )


@pytest.mark.anyio
async def test_get_actors_x(trust_registry_client: RichAsyncClient):
    with pytest.raises(HTTPException) as exc:
        await trust_registry_client.get(
            f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_name=Bad_actor_name"
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await trust_registry_client.get(
            f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_id=Bad_actor_id"
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await trust_registry_client.get(
            f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_did=Bad_actor_did"
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await trust_registry_client.get(
            f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors?actor_did=Bad&actor_id=Request"
        )
    assert exc.value.status_code == 400


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_issuers(
    faber_indy_issuer: CreateTenantResponse,  # pylint: disable=unused-argument
    trust_registry_client: RichAsyncClient,
):
    actors = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors/issuers"
    )
    assert actors.status_code == 200


@pytest.mark.anyio
async def test_get_verifiers(
    acme_verifier: CreateTenantResponse,  # pylint: disable=unused-argument
    trust_registry_client: RichAsyncClient,
):
    actors = await trust_registry_client.get(
        f"{CLOUDAPI_TRUST_REGISTRY_PATH}/actors/verifiers"
    )
    assert actors.status_code == 200

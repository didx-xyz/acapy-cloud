import pytest
from aries_cloudcontroller import AcaPyClient

from app.dependencies.auth import (
    acapy_auth_from_header,
    acapy_auth_verified,
)
from app.routes import definitions
from app.routes.definitions import (
    CreateCredentialDefinition,
    CredentialSchema,
)
from app.routes.definitions import router as definitions_router
from app.services.acapy_wallet import get_public_did
from app.services.trust_registry.util.schema import registry_has_schema
from app.tests.util.regression_testing import TestMode
from app.util.string import random_string
from shared import RichAsyncClient

DEFINITIONS_BASE_PATH = definitions_router.prefix


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_create_anoncreds_schema(
    anoncreds_schema_definition: CredentialSchema,
):
    expected_schema_name = (
        "test_anoncreds_schema"
        if TestMode.clean_run in TestMode.fixture_params
        else "Regression_test_anoncreds_schema"  # Regression run uses a different name
    )
    assert anoncreds_schema_definition.name == expected_schema_name
    assert set(anoncreds_schema_definition.attribute_names) == {"speed", "name", "age"}
    assert anoncreds_schema_definition.version  # It's random


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_anoncreds_schema(
    anoncreds_schema_definition: CredentialSchema,
    faber_anoncreds_client: RichAsyncClient,
    meld_co_anoncreds_client: RichAsyncClient,
):
    schema_id = anoncreds_schema_definition.id
    schema_name = anoncreds_schema_definition.name
    schema_version = anoncreds_schema_definition.version
    schema_attributes = anoncreds_schema_definition.attribute_names

    def assert_schema_response(schema_response: dict):
        # Helper method to assert schema response has expected values
        assert schema_response["id"] == schema_id
        assert schema_response["name"] == schema_name
        assert schema_response["version"] == schema_version
        assert set(schema_response["attribute_names"]) == set(schema_attributes)

    # First of all, assert schema is on the trust registry
    assert await registry_has_schema(schema_id)

    # Faber can fetch their own schema
    schema_response = await faber_anoncreds_client.get(
        f"{DEFINITIONS_BASE_PATH}/schemas/{schema_id}"
    )
    schema_response = schema_response.json()
    assert_schema_response(schema_response)

    # Another AnonCreds issuer can also fetch the same schema
    schema_response = await meld_co_anoncreds_client.get(
        f"{DEFINITIONS_BASE_PATH}/schemas/{schema_id}"
    )
    schema_response = schema_response.json()
    assert_schema_response(schema_response)

    # Note: Indy issuers can fetch AnonCreds schemas as well


@pytest.mark.anyio
@pytest.mark.parametrize("support_revocation", [False, True])
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_create_anoncreds_credential_definition(
    anoncreds_schema_definition: CredentialSchema,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_client: RichAsyncClient,
    support_revocation: bool,
):
    schema_id = anoncreds_schema_definition.id
    tag = random_string(5)
    credential_definition = CreateCredentialDefinition(
        schema_id=schema_id,
        tag=tag,
        support_revocation=support_revocation,
    )

    auth = acapy_auth_verified(
        acapy_auth_from_header(faber_anoncreds_client.headers["x-api-key"])
    )

    result = (
        await definitions.create_credential_definition(
            credential_definition=credential_definition, auth=auth
        )
    ).model_dump()

    faber_public_did = await get_public_did(faber_anoncreds_acapy_client)

    assert result["id"].split("/")[0] == schema_id.split("/")[0]  # DID match
    assert result["schema_id"] == schema_id

    cred_def_id = result["id"]
    get_cred_def_result = (
        await definitions.get_credential_definition_by_id(cred_def_id, auth)
    ).model_dump()

    assert get_cred_def_result["tag"] == tag
    assert get_cred_def_result["schema_id"] == schema_id

    if support_revocation:
        # Assert that revocation registry was created
        rev_reg_result = await faber_anoncreds_acapy_client.anoncreds_revocation.get_active_revocation_registry(
            cred_def_id
        )
        issuer_rev_reg_record = rev_reg_result.result
        assert issuer_rev_reg_record
        assert cred_def_id == issuer_rev_reg_record.cred_def_id
        assert issuer_rev_reg_record.issuer_did == faber_public_did.did

        revocation_registries = (
            await faber_anoncreds_acapy_client.anoncreds_revocation.get_revocation_registries(
                cred_def_id=cred_def_id
            )
        ).rev_reg_ids

        # There should be two revocation registries, assert at least one exists
        # one being used to issue credentials against and once full with to the next one
        assert len(revocation_registries) >= 1

import pytest
from aries_cloudcontroller import AcaPyClient

from app.dependencies.auth import (
    AcaPyAuthVerified,
    acapy_auth_from_header,
    acapy_auth_verified,
)
from app.models.definitions import SchemaType
from app.routes import definitions
from app.routes.definitions import (
    CreateCredentialDefinition,
    CreateSchema,
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
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Don't create new schemas in regression mode",
)
async def test_create_schema(
    governance_public_did: str, mock_governance_auth: AcaPyAuthVerified
):
    send = CreateSchema(
        schema_type=SchemaType.INDY,
        name=random_string(15),
        version="0.1",
        attribute_names=["average"],
    )

    result = (await definitions.create_schema(send, mock_governance_auth)).model_dump()

    # Assert schemas has been registered in the trust registry
    assert await registry_has_schema(result["id"])
    expected_schema = f"{governance_public_did}:2:{send.name}:{send.version}"
    assert result["id"] == expected_schema
    assert result["name"] == send.name
    assert result["version"] == send.version
    assert set(result["attribute_names"]) == set(send.attribute_names)


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
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Don't create new schemas in regression mode",
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_schema(
    governance_public_did: str,
    mock_governance_auth: AcaPyAuthVerified,
    faber_indy_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
):
    # given
    schema = CreateSchema(
        name=random_string(15), version="0.1", attribute_names=["average"]
    )
    schema_name = schema.name
    schema_version = schema.version
    schema_attributes = schema.attribute_names

    def assert_schema_response(schema_response: CredentialSchema):
        # Helper method to assert schema response has expected values
        assert schema_response.id == schema_id
        assert schema_response.name == schema_name
        assert schema_response.version == schema_version
        assert set(schema_response.attribute_names) == set(schema_attributes)

    create_result = await definitions.create_schema(schema, mock_governance_auth)

    schema_id = create_result.id

    expected_schema_id = f"{governance_public_did}:2:{schema.name}:{schema.version}"
    assert schema_id == expected_schema_id

    # Assert schema is on the trust registry
    assert await registry_has_schema(schema_id)

    # The schema can be fetched by governance
    result = await definitions.get_schema(schema_id, mock_governance_auth)
    assert_schema_response(result)

    # The schema can be fetched by Indy issuers
    auth = acapy_auth_from_header(faber_indy_client.headers["x-api-key"])
    result = await definitions.get_schema(schema_id, auth)
    assert_schema_response(result)

    # The schema can be fetched by AnonCreds issuers
    auth = acapy_auth_from_header(faber_anoncreds_client.headers["x-api-key"])
    result = await definitions.get_schema(schema_id, auth)
    assert_schema_response(result)


@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_get_anoncreds_schema(
    anoncreds_schema_definition: CredentialSchema,
    faber_anoncreds_client: RichAsyncClient,
    meld_co_anoncreds_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
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

    # Indy issuers can fetch AnonCreds schemas as well
    schema_response = await faber_indy_client.get(
        f"{DEFINITIONS_BASE_PATH}/schemas/{schema_id}"
    )
    schema_response = schema_response.json()
    assert_schema_response(schema_response)


@pytest.mark.anyio
@pytest.mark.parametrize("support_revocation", [False, True])
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=(
        "Mystery -- this test passes continuously if it's the only test, "
        "but it fails when run a 2nd time in regression mode"
    ),
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_create_credential_definition(
    indy_schema_definition: CredentialSchema,
    faber_indy_acapy_client: AcaPyClient,
    faber_indy_client: RichAsyncClient,
    support_revocation: bool,
):
    schema_id = indy_schema_definition.id
    tag = random_string(5)
    credential_definition = CreateCredentialDefinition(
        schema_id=schema_id,
        tag=tag,
        support_revocation=support_revocation,
    )

    auth = acapy_auth_verified(
        acapy_auth_from_header(faber_indy_client.headers["x-api-key"])
    )

    result = (
        await definitions.create_credential_definition(
            credential_definition=credential_definition, auth=auth
        )
    ).model_dump()

    faber_public_did = await get_public_did(faber_indy_acapy_client)
    schema = await faber_indy_acapy_client.schema.get_schema(schema_id=schema_id)

    assert (
        result["id"] == f"{faber_public_did.did}:3:CL:{schema.var_schema.seq_no}:{tag}"
    )
    assert result["tag"] == tag
    assert result["schema_id"] == schema_id

    get_cred_def_result = (
        await definitions.get_credential_definition_by_id(result["id"], auth)
    ).model_dump()

    assert get_cred_def_result["tag"] == tag
    assert get_cred_def_result["schema_id"] == schema_id

    if support_revocation:
        cred_def_id = result["id"]
        # Assert that revocation registry was created
        rev_reg_result = (
            await faber_indy_acapy_client.revocation.get_active_registry_for_cred_def(
                cred_def_id=cred_def_id
            )
        )
        issuer_rev_reg_record = rev_reg_result.result
        assert issuer_rev_reg_record
        assert cred_def_id == issuer_rev_reg_record.cred_def_id
        assert issuer_rev_reg_record.issuer_did == faber_public_did.did

        revocation_registries = (
            await faber_indy_acapy_client.revocation.get_created_registries(
                cred_def_id=cred_def_id
            )
        ).rev_reg_ids

        # There should be two revocation registries, assert at least one exists
        # one being used to issue credentials against and once full with to the next one
        assert len(revocation_registries) >= 1


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
    schema = await faber_anoncreds_acapy_client.anoncreds_schemas.get_schema(
        schema_id=schema_id
    )

    assert (
        result["id"]
        == f"{faber_public_did.did}:3:CL:{schema.schema_metadata['seqNo']}:{tag}"
    )
    assert result["tag"] == tag
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

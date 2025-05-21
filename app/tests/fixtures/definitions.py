import pytest

from app.models.definitions import CredentialDefinition
from app.routes.definitions import (
    CreateCredentialDefinition,
    CreateSchema,
    CredentialSchema,
)
from app.routes.definitions import router as definitions_router
from app.tests.util.regression_testing import (
    TestMode,
    assert_fail_on_recreating_fixtures,
)
from app.util.string import random_version
from shared import RichAsyncClient

DEFINITIONS_BASE_PATH = definitions_router.prefix


async def fetch_or_create_regression_test_schema_definition(
    name: str,
    faber_client: RichAsyncClient,  # Used for fetching the schema
    governance_client: RichAsyncClient,  # Used for creating the schema
) -> CredentialSchema:
    regression_test_schema_name = "Regression_" + name

    response = await faber_client.get(
        f"{DEFINITIONS_BASE_PATH}/schemas?schema_name={regression_test_schema_name}",
    )
    schemas = response.json()
    num_schemas = len(schemas)
    assert (
        num_schemas < 2
    ), f"Should have 1 or 0 schemas with this name, got: {num_schemas}"

    if schemas:
        schema_definition_result = schemas[0]
    else:
        # Schema not created yet
        assert_fail_on_recreating_fixtures()
        definition = CreateSchema(
            name=regression_test_schema_name,
            version="1.0.0",
            attribute_names=["speed", "name", "age"],
        )

        schema_definition_response = await governance_client.post(
            DEFINITIONS_BASE_PATH + "/schemas", json=definition.model_dump()
        )
        schema_definition_result = schema_definition_response.json()
    return CredentialSchema.model_validate(schema_definition_result)


async def get_clean_or_regression_test_schema(
    name: str,
    faber_client: RichAsyncClient,
    test_mode: str,
    governance_client: RichAsyncClient,
):
    if test_mode == TestMode.clean_run:
        definition = CreateSchema(
            name=name,
            version=random_version(),
            attribute_names=["speed", "name", "age"],
        )

        schema_definition_response = await governance_client.post(
            DEFINITIONS_BASE_PATH + "/schemas", json=definition.model_dump()
        )
        schema_definition_result = CredentialSchema.model_validate(
            schema_definition_response.json()
        )
    elif test_mode == TestMode.regression_run:
        schema_definition_result = (
            await fetch_or_create_regression_test_schema_definition(
                name, faber_client, governance_client
            )
        )
    else:
        raise ValueError(f"Bad test mode: {test_mode}")

    return schema_definition_result


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def anoncreds_schema_definition(
    request,
    faber_anoncreds_client: RichAsyncClient,
    governance_client: RichAsyncClient,
) -> CredentialSchema:

    return await get_clean_or_regression_test_schema(
        name="test_anoncreds_schema",
        faber_client=faber_anoncreds_client,
        governance_client=governance_client,
        test_mode=request.param,
    )


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def anoncreds_schema_definition_alt(
    request,
    faber_anoncreds_client: RichAsyncClient,
    governance_client: RichAsyncClient,
) -> CredentialSchema:
    return await get_clean_or_regression_test_schema(
        name="test_anoncreds_schema_alt",
        faber_client=faber_anoncreds_client,
        governance_client=governance_client,
        test_mode=request.param,
    )


async def fetch_or_create_regression_test_cred_def(
    client: RichAsyncClient, schema: CredentialSchema, support_revocation: bool
):
    regression_test_cred_def_tag = "RegressionTestTag"
    schema_id = schema.id

    cred_defs_response = await client.get(
        f"{DEFINITIONS_BASE_PATH}/credentials?schema_id={schema_id}"
    )
    cred_defs = cred_defs_response.json()
    print("Cred defs:", cred_defs)
    filtered_cred_defs = [
        cred_def
        for cred_def in cred_defs
        if cred_def["tag"] == regression_test_cred_def_tag
    ]

    num_cred_defs = len(filtered_cred_defs)
    assert (
        num_cred_defs < 2
    ), f"Should have 1 or 0 cred defs with this tag, got: {num_cred_defs}"

    if filtered_cred_defs:
        result = filtered_cred_defs[0]
    else:
        # Cred defs not created yet
        assert_fail_on_recreating_fixtures()

        definition = CreateCredentialDefinition(
            tag=regression_test_cred_def_tag,
            schema_id=schema.id,
            support_revocation=support_revocation,
        )
        response = await client.post(
            DEFINITIONS_BASE_PATH + "/credentials",
            json=definition.model_dump(),
        )
        result = response.json()
    return result


async def get_clean_or_regression_test_cred_def(
    test_mode: str,
    client: RichAsyncClient,
    schema: CredentialSchema,
    support_revocation: bool,
) -> CredentialDefinition:
    if test_mode == TestMode.clean_run:
        definition = CreateCredentialDefinition(
            tag="tag",
            schema_id=schema.id,
            support_revocation=support_revocation,
        )
        response = await client.post(
            DEFINITIONS_BASE_PATH + "/credentials",
            json=definition.model_dump(),
        )
        result = response.json()
    elif test_mode == TestMode.regression_run:
        result = await fetch_or_create_regression_test_cred_def(
            client=client, schema=schema, support_revocation=support_revocation
        )
    else:
        raise ValueError(f"Bad test mode: {test_mode}")

    return CredentialDefinition.model_validate(result)


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def anoncreds_credential_definition_id(
    request,
    anoncreds_schema_definition: CredentialSchema,  # pylint: disable=redefined-outer-name
    faber_anoncreds_client: RichAsyncClient,
) -> str:
    result = await get_clean_or_regression_test_cred_def(
        test_mode=request.param,
        client=faber_anoncreds_client,
        schema=anoncreds_schema_definition,
        support_revocation=False,
    )
    return result.id


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def anoncreds_credential_definition_id_revocable(
    request,
    anoncreds_schema_definition_alt: CredentialSchema,  # pylint: disable=redefined-outer-name
    faber_anoncreds_client: RichAsyncClient,
) -> str:
    result = await get_clean_or_regression_test_cred_def(
        test_mode=request.param,
        client=faber_anoncreds_client,
        schema=anoncreds_schema_definition_alt,
        support_revocation=True,
    )
    return result.id


@pytest.fixture(scope="session", params=TestMode.fixture_params)
async def meld_co_anoncreds_credential_definition_id(
    request,
    anoncreds_schema_definition: CredentialSchema,  # pylint: disable=redefined-outer-name
    meld_co_anoncreds_client: RichAsyncClient,
) -> str:

    result = await get_clean_or_regression_test_cred_def(
        test_mode=request.param,
        client=meld_co_anoncreds_client,
        schema=anoncreds_schema_definition,
        support_revocation=False,
    )
    return result.id

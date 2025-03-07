import pytest
from aries_cloudcontroller import AcaPyClient
from assertpy import assert_that

from app.dependencies.auth import (
    AcaPyAuthVerified,
    acapy_auth_from_header,
    acapy_auth_verified,
)
from app.routes import definitions
from app.routes.definitions import (
    CreateCredentialDefinition,
    CreateSchema,
    CredentialSchema,
)
from app.services.acapy_wallet import get_public_did
from app.services.trust_registry.util.schema import registry_has_schema
from app.tests.util.regression_testing import TestMode
from app.util.string import random_string
from shared import RichAsyncClient


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Don't create new schemas in regression mode",
)
async def test_create_schema(
    governance_public_did: str, mock_governance_auth: AcaPyAuthVerified
):
    send = CreateSchema(
        name=random_string(15), version="0.1", attribute_names=["average"]
    )

    result = (await definitions.create_schema(send, mock_governance_auth)).model_dump()

    # Assert schemas has been registered in the trust registry
    assert await registry_has_schema(result["id"])
    expected_schema = f"{governance_public_did}:2:{send.name}:{send.version}"
    assert_that(result).has_id(expected_schema)
    assert_that(result).has_name(send.name)
    assert_that(result).has_version(send.version)
    assert_that(result).has_attribute_names(send.attribute_names)


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason="Don't create new schemas in regression mode",
)
async def test_get_schema(
    governance_public_did: str, mock_governance_auth: AcaPyAuthVerified
):
    # given
    schema = CreateSchema(
        name=random_string(15), version="0.1", attribute_names=["average"]
    )

    create_result = (
        await definitions.create_schema(schema, mock_governance_auth)
    ).model_dump()
    result = await definitions.get_schema(create_result["id"], mock_governance_auth)

    assert await registry_has_schema(result.id)
    expected_schema = f"{governance_public_did}:2:{schema.name}:{schema.version}"
    assert_that(result).has_id(expected_schema)
    assert_that(result).has_name(schema.name)
    assert_that(result).has_version(schema.version)
    assert_that(result).has_attribute_names(schema.attribute_names)


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

    assert_that(result).has_id(
        f"{faber_public_did.did}:3:CL:{schema.var_schema.seq_no}:{tag}"
    )
    assert_that(result).has_tag(tag)
    assert_that(result).has_schema_id(schema_id)

    get_cred_def_result = (
        await definitions.get_credential_definition_by_id(result["id"], auth)
    ).model_dump()

    assert_that(get_cred_def_result).has_tag(tag)
    assert_that(get_cred_def_result).has_schema_id(schema_id)

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

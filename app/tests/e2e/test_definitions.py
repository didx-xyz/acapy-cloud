import pytest
from aries_cloudcontroller import AcaPyClient
from assertpy import assert_that

from app.dependencies import acapy_auth, acapy_auth_verified
from app.facades import trust_registry
from app.facades.acapy_wallet import get_public_did
from app.generic import definitions
from app.generic.definitions import (CreateCredentialDefinition, CreateSchema,
                                     CredentialSchema)
from app.tests.util.string import get_random_string
from app.tests.util.trust_registry import register_issuer
from app.util.rich_async_client import RichAsyncClient


@pytest.mark.anyio
async def test_create_credential_definition(
    governance_acapy_client: AcaPyClient, governance_client: RichAsyncClient
):
    # given
    schema = CreateSchema(
        name=get_random_string(15), version="0.1", attribute_names=["average"]
    )

    schema_result = (
        await definitions.create_schema(schema, governance_acapy_client)
    ).dict()
    schema_id = schema_result["id"]

    credential_definition = CreateCredentialDefinition(
        schema_id=schema_id, tag=get_random_string(5), support_revocation=True
    )

    auth = acapy_auth_verified(acapy_auth(governance_client.headers["x-api-key"]))

    # when
    result = (
        await definitions.create_credential_definition(
            credential_definition, governance_acapy_client, auth
        )
    ).dict()

    assert_that(result).has_tag(credential_definition.tag)
    assert_that(result).has_schema_id(credential_definition.schema_id)
    assert_that(result["id"]).is_not_empty()


@pytest.mark.anyio
async def test_create_schema(
    governance_acapy_client: AcaPyClient, governance_public_did: str
):
    # given
    send = CreateSchema(
        name=get_random_string(15), version="0.1", attribute_names=["average"]
    )

    result = (await definitions.create_schema(send, governance_acapy_client)).dict()

    # Assert schemas has been registered in the trust registry
    assert await trust_registry.registry_has_schema(result["id"])
    expected_schema = f"{governance_public_did}:2:{send.name}:{send.version}"
    assert_that(result).has_id(expected_schema)
    assert_that(result).has_name(send.name)
    assert_that(result).has_version(send.version)
    assert_that(result).has_attribute_names(send.attribute_names)


@pytest.mark.anyio
async def test_get_schema(
    governance_acapy_client: AcaPyClient, governance_public_did: str
):
    # given
    schema = CreateSchema(
        name=get_random_string(15), version="0.1", attribute_names=["average"]
    )

    create_result = (
        await definitions.create_schema(schema, governance_acapy_client)
    ).dict()
    result = await definitions.get_schema(create_result["id"], governance_acapy_client)

    assert await trust_registry.registry_has_schema(result.id)
    expected_schema = f"{governance_public_did}:2:{schema.name}:{schema.version}"
    assert_that(result).has_id(expected_schema)
    assert_that(result).has_name(schema.name)
    assert_that(result).has_version(schema.version)
    assert_that(result).has_attribute_names(schema.attribute_names)


@pytest.mark.anyio
async def test_get_credential_definition(
    governance_acapy_client: AcaPyClient, governance_client: RichAsyncClient
):
    # given
    schema_send = CreateSchema(
        name=get_random_string(15), version="0.1", attribute_names=["average"]
    )

    schema_result = (
        await definitions.create_schema(schema_send, governance_acapy_client)
    ).dict()

    await register_issuer(governance_client, schema_result["id"])
    credential_definition = CreateCredentialDefinition(
        schema_id=schema_result["id"], tag=get_random_string(5)
    )

    auth = acapy_auth_verified(acapy_auth(governance_client.headers["x-api-key"]))

    # when
    create_result = (
        await definitions.create_credential_definition(
            credential_definition, governance_acapy_client, auth
        )
    ).dict()

    result = (
        await definitions.get_credential_definition_by_id(
            create_result["id"], governance_acapy_client
        )
    ).dict()

    assert_that(result).has_tag(credential_definition.tag)
    assert_that(result).has_schema_id(credential_definition.schema_id)
    assert_that(result["id"]).is_not_empty()


@pytest.mark.anyio
async def test_create_credential_definition_issuer_tenant(
    schema_definition: CredentialSchema,
    faber_acapy_client: AcaPyClient,
    faber_client: RichAsyncClient,
):
    credential_definition = CreateCredentialDefinition(
        schema_id=schema_definition.id,
        tag=get_random_string(5),
        support_revocation=True,
    )

    auth = acapy_auth_verified(acapy_auth(faber_client.headers["x-api-key"]))

    # when
    result = (
        await definitions.create_credential_definition(
            credential_definition, faber_acapy_client, auth
        )
    ).dict()

    faber_public_did = await get_public_did(faber_acapy_client)
    schema = await faber_acapy_client.schema.get_schema(schema_id=schema_definition.id)

    assert_that(result).has_id(
        f"{faber_public_did.did}:3:CL:{schema.schema_.seq_no}:{credential_definition.tag}"
    )
    assert_that(result).has_tag(credential_definition.tag)

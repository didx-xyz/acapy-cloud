import pytest

from app.models.tenants import CreateTenantResponse
from app.routes.connections import router as conn_router
from app.tests.util.connections import (
    AcmeAliceConnect,
    BobAliceConnect,
    FaberAliceConnect,
    MeldCoAliceConnect,
    connect_using_trust_registry_invite,
    create_connection_by_test_mode,
    fetch_or_create_trust_registry_connection,
)
from app.tests.util.regression_testing import RegressionTestConfig, TestMode
from shared import RichAsyncClient

CONNECTIONS_BASE_PATH = conn_router.prefix


# Fixture for passing test mode params. Assists with mixing direct and indirect request
@pytest.fixture(scope="module", params=TestMode.fixture_params)
async def test_mode(request) -> str:
    return request.param


@pytest.fixture(scope="function")
async def bob_and_alice_connection(
    bob_member_client: RichAsyncClient,
    alice_member_client: RichAsyncClient,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> BobAliceConnect:
    return await create_connection_by_test_mode(
        test_mode=test_mode,
        alice_member_client=alice_member_client,
        bob_member_client=bob_member_client,
        alias="AliceBobConnection",
    )


@pytest.fixture(scope="function")
async def faber_anoncreds_and_alice_connection(
    alice_member_client: RichAsyncClient,
    alice_tenant: CreateTenantResponse,
    faber_anoncreds_client: RichAsyncClient,
    faber_anoncreds_issuer: CreateTenantResponse,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> FaberAliceConnect:
    connection_alias = "AliceFaberTrustRegistryConnection"

    if test_mode == TestMode.clean_run:
        faber_alice_connect = await connect_using_trust_registry_invite(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            actor_client=faber_anoncreds_client,
            actor=faber_anoncreds_issuer,
            connection_alias=connection_alias,
        )
    elif test_mode == TestMode.regression_run:
        connection_alias_prefix = RegressionTestConfig.reused_connection_alias

        faber_alice_connect = await fetch_or_create_trust_registry_connection(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            actor_client=faber_anoncreds_client,
            actor=faber_anoncreds_issuer,
            connection_alias=f"{connection_alias_prefix}-{connection_alias}",
        )
    else:
        raise AssertionError(f"unknown test mode: {test_mode}")

    return FaberAliceConnect(
        alice_connection_id=faber_alice_connect.alice_connection_id,
        faber_connection_id=faber_alice_connect.bob_connection_id,
    )


@pytest.fixture(scope="function")
async def acme_and_alice_connection(
    alice_member_client: RichAsyncClient,
    alice_tenant: CreateTenantResponse,
    acme_client: RichAsyncClient,
    acme_verifier: CreateTenantResponse,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> AcmeAliceConnect:
    # Check if request param comes indirectly from higher fixture to establish trust registry connection instead
    connection_alias = "AliceAcmeTrustRegistryConnection"

    if test_mode == TestMode.clean_run:
        acme_alice_connect = await connect_using_trust_registry_invite(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            actor_client=acme_client,
            actor=acme_verifier,
            connection_alias=connection_alias,
        )
    elif test_mode == TestMode.regression_run:
        connection_alias_prefix = RegressionTestConfig.reused_connection_alias

        acme_alice_connect = await fetch_or_create_trust_registry_connection(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            actor_client=acme_client,
            actor=acme_verifier,
            connection_alias=f"{connection_alias_prefix}-{connection_alias}",
        )
    else:
        raise AssertionError(f"unknown test mode: {test_mode}")

    return AcmeAliceConnect(
        alice_connection_id=acme_alice_connect.alice_connection_id,
        acme_connection_id=acme_alice_connect.bob_connection_id,
    )


# Create fixture to handle parameters and return either meld_co-alice connection fixture
@pytest.fixture(scope="function")
async def meld_co_anoncreds_and_alice_connection(
    request,
    alice_tenant: CreateTenantResponse,
    alice_member_client: RichAsyncClient,
    meld_co_anoncreds_client: RichAsyncClient,
    meld_co_anoncreds_issuer_verifier: CreateTenantResponse,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> MeldCoAliceConnect:
    if hasattr(request, "param") and request.param == "trust_registry":
        connection_alias = "AliceMeldCoAnonCredsTrustRegistryConnection"

        if test_mode == TestMode.clean_run:
            meld_co_alice_connect = await connect_using_trust_registry_invite(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                actor_client=meld_co_anoncreds_client,
                actor=meld_co_anoncreds_issuer_verifier,
                connection_alias=connection_alias,
            )
        elif test_mode == TestMode.regression_run:
            connection_alias_prefix = RegressionTestConfig.reused_connection_alias

            meld_co_alice_connect = await fetch_or_create_trust_registry_connection(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                actor_client=meld_co_anoncreds_client,
                actor=meld_co_anoncreds_issuer_verifier,
                connection_alias=f"{connection_alias_prefix}-{connection_alias}",
            )
        else:
            raise AssertionError(f"unknown test mode: {test_mode}")
    else:
        # No indirect request param for trust registry connection; establish normal connection:
        meld_co_alice_connect = await create_connection_by_test_mode(
            test_mode=test_mode,
            alice_member_client=alice_member_client,
            bob_member_client=meld_co_anoncreds_client,
            alias="AliceMeldCoAnonCredsConnection",
        )

    return MeldCoAliceConnect(
        alice_connection_id=meld_co_alice_connect.alice_connection_id,
        meld_co_connection_id=meld_co_alice_connect.bob_connection_id,
    )

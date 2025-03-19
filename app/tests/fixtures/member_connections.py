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
async def faber_indy_and_alice_connection(
    alice_member_client: RichAsyncClient,
    faber_indy_client: RichAsyncClient,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> FaberAliceConnect:
    bob_alice_connection = await create_connection_by_test_mode(
        test_mode=test_mode,
        alice_member_client=alice_member_client,
        bob_member_client=faber_indy_client,
        alias="AliceFaberIndyConnection",
        did_exchange=True,
    )

    return FaberAliceConnect(
        alice_connection_id=bob_alice_connection.alice_connection_id,
        faber_connection_id=bob_alice_connection.bob_connection_id,
    )


@pytest.fixture(scope="function")
async def faber_anoncreds_and_alice_connection(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_client: RichAsyncClient,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> FaberAliceConnect:
    bob_alice_connection = await create_connection_by_test_mode(
        test_mode=test_mode,
        alice_member_client=alice_member_client,
        bob_member_client=faber_anoncreds_client,
        alias="AliceFaberAnonCredsConnection",
        did_exchange=True,
    )

    return FaberAliceConnect(
        alice_connection_id=bob_alice_connection.alice_connection_id,
        faber_connection_id=bob_alice_connection.bob_connection_id,
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
            verifier_client=acme_client,
            verifier=acme_verifier,
            connection_alias=connection_alias,
        )
    elif test_mode == TestMode.regression_run:
        connection_alias_prefix = RegressionTestConfig.reused_connection_alias

        acme_alice_connect = await fetch_or_create_trust_registry_connection(
            alice_member_client=alice_member_client,
            alice_tenant=alice_tenant,
            verifier_client=acme_client,
            verifier=acme_verifier,
            connection_alias=f"{connection_alias_prefix}-{connection_alias}",
        )
    else:
        assert False, f"unknown test mode: {test_mode}"

    return acme_alice_connect


# Create fixture to handle parameters and return either meld_co-alice connection fixture
@pytest.fixture(scope="function")
async def meld_co_indy_and_alice_connection(
    request,
    alice_tenant: CreateTenantResponse,
    alice_member_client: RichAsyncClient,
    meld_co_indy_client: RichAsyncClient,
    meld_co_indy_issuer_verifier: CreateTenantResponse,
    test_mode: str,  # pylint: disable=redefined-outer-name
) -> MeldCoAliceConnect:
    if hasattr(request, "param") and request.param == "trust_registry":
        connection_alias = "AliceMeldCoIndyTrustRegistryConnection"

        if test_mode == TestMode.clean_run:
            acme_alice_connect = await connect_using_trust_registry_invite(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                verifier_client=meld_co_indy_client,
                verifier=meld_co_indy_issuer_verifier,
                connection_alias=connection_alias,
            )
        elif test_mode == TestMode.regression_run:
            connection_alias_prefix = RegressionTestConfig.reused_connection_alias

            acme_alice_connect = await fetch_or_create_trust_registry_connection(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                verifier_client=meld_co_indy_client,
                verifier=meld_co_indy_issuer_verifier,
                connection_alias=f"{connection_alias_prefix}-{connection_alias}",
            )
        else:
            assert False, f"unknown test mode: {test_mode}"

        return MeldCoAliceConnect(
            alice_connection_id=acme_alice_connect.alice_connection_id,
            meld_co_connection_id=acme_alice_connect.acme_connection_id,
        )
    else:
        # No indirect request param for trust registry connection; establish normal connection:
        bob_alice_connection = await create_connection_by_test_mode(
            test_mode=test_mode,
            alice_member_client=alice_member_client,
            bob_member_client=meld_co_indy_client,
            alias="AliceMeldCoIndyConnection",
            did_exchange=True,
        )

        return MeldCoAliceConnect(
            alice_connection_id=bob_alice_connection.alice_connection_id,
            meld_co_connection_id=bob_alice_connection.bob_connection_id,
        )


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
            acme_alice_connect = await connect_using_trust_registry_invite(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                verifier_client=meld_co_anoncreds_client,
                verifier=meld_co_anoncreds_issuer_verifier,
                connection_alias=connection_alias,
            )
        elif test_mode == TestMode.regression_run:
            connection_alias_prefix = RegressionTestConfig.reused_connection_alias

            acme_alice_connect = await fetch_or_create_trust_registry_connection(
                alice_member_client=alice_member_client,
                alice_tenant=alice_tenant,
                verifier_client=meld_co_anoncreds_client,
                verifier=meld_co_anoncreds_issuer_verifier,
                connection_alias=f"{connection_alias_prefix}-{connection_alias}",
            )
        else:
            assert False, f"unknown test mode: {test_mode}"

        return MeldCoAliceConnect(
            alice_connection_id=acme_alice_connect.alice_connection_id,
            meld_co_connection_id=acme_alice_connect.acme_connection_id,
        )
    else:
        # No indirect request param for trust registry connection; establish normal connection:
        bob_alice_connection = await create_connection_by_test_mode(
            test_mode=test_mode,
            alice_member_client=alice_member_client,
            bob_member_client=meld_co_anoncreds_client,
            alias="AliceMeldCoAnonCredsConnection",
            did_exchange=True,
        )

        return MeldCoAliceConnect(
            alice_connection_id=bob_alice_connection.alice_connection_id,
            meld_co_connection_id=bob_alice_connection.bob_connection_id,
        )

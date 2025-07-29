"""Testing revocation registry lifecycle management and recovery."""

import asyncio
import os

import pytest

from app.models.definitions import CreateCredentialDefinition
from app.models.tenants import CreateTenantResponse
from app.services.revocation_registry import wait_for_active_registry
from app.tests.fixtures.definitions import (
    DEFINITIONS_BASE_PATH,
    fetch_or_create_regression_test_schema_definition,
)
from app.tests.fixtures.member_acapy_clients import get_token
from app.tests.resilience_testing.resilience_test_utils import LogPatternMonitor
from app.tests.util.client import (
    get_governance_client,
    get_tenant_acapy_client,
    get_tenant_admin_client,
    get_tenant_client,
)
from app.tests.util.connections import (
    BobAliceConnect,
    FaberAliceConnect,
    create_bob_alice_connection,
)
from app.tests.util.issuer import issue_single_credential, revoke_single_credential
from app.tests.util.regression_testing import get_or_create_tenant
from app.tests.util.verifier import send_proof_and_assert_verified
from app.util.string import random_string
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

MONITOR_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "monitor_and_kill_pod.sh")
CREDENTIALS_BASE_PATH = "/v1/issuer/credentials"

LOGGER = get_logger(__name__)


@pytest.mark.anyio
@pytest.mark.skip(reason="Test is for local testing only")
async def test_rev_reg_resilience():
    # Create schema
    governance_client = get_governance_client()
    schema_name = "test_rev_reg_resilience"
    schema_definition = await fetch_or_create_regression_test_schema_definition(
        schema_name, governance_client, governance_client
    )
    LOGGER.info(f"Schema created/fetched: {schema_name}")

    # Create a issuer/verifier tenant (both roles)
    admin_client = get_tenant_admin_client()
    issuer_name = "ResilienceTestIssuerVerifier" + random_string(5)
    issuer_verifier_tenant = await get_or_create_tenant(
        admin_client=admin_client,
        name=issuer_name,
        roles=["issuer", "verifier"],
    )
    issuer_token = issuer_verifier_tenant.access_token
    issuer_client = get_tenant_client(token=issuer_token, name="Issuer")
    issuer_client.raise_status_error = False
    LOGGER.info(f"Issuer/verifier tenant created: {issuer_name}")

    # Create 10 holders
    holders = []
    connections = []
    for i in range(10):
        holder_name = f"ResilienceTestHolder{i}_" + random_string(5)
        holder_tenant: CreateTenantResponse = await get_or_create_tenant(
            admin_client=admin_client, name=holder_name, roles=[]
        )
        holder_client: RichAsyncClient = get_tenant_client(
            token=holder_tenant.access_token, name=f"Holder{i}"
        )
        holders.append(holder_client)
        LOGGER.info(f"\tHolder {i} tenant created: {holder_name}")

        # Create connection between issuer and this holder
        await asyncio.sleep(1.5)
        connection_alias = f"ResilienceTestConnection{i}_" + random_string(5)
        connection: BobAliceConnect = await create_bob_alice_connection(
            alice_member_client=holder_client,
            bob_member_client=issuer_client,
            alias=connection_alias,
        )
        faber_alice_connection = FaberAliceConnect(
            alice_connection_id=connection.alice_connection_id,
            faber_connection_id=connection.bob_connection_id,
        )
        connections.append(
            {"bob_alice": connection, "faber_alice": faber_alice_connection}
        )
        LOGGER.info(f"\tConnection {i} created: {connection_alias}")

    # Start pod monitor-and-kill script
    monitor = LogPatternMonitor(MONITOR_SCRIPT_PATH)
    monitor.start_monitoring()

    # Issuer creates credential definition (revocable)
    LOGGER.info("Creating credential definition")
    cred_def_tag = "ResilienceTestCredDef" + random_string(5)
    cred_def_request = CreateCredentialDefinition(
        tag=cred_def_tag,
        schema_id=schema_definition.id,
        support_revocation=True,
    )
    create_cred_def_response = await issuer_client.post(
        f"{DEFINITIONS_BASE_PATH}/credentials", json=cred_def_request.model_dump()
    )

    # Monitor script should interrupt agent before request completes
    # Issuer should get a timeout on their initial cred def create request
    LOGGER.info(f"Create cred def status code: {create_cred_def_response.status_code}")
    LOGGER.info(f"Create cred def response: {create_cred_def_response.text}")
    assert create_cred_def_response.status_code / 100 == 5, "Expected 5xx error"

    # Agent should be restarting
    LOGGER.info("Waiting 30 seconds for agent to restart")
    await asyncio.sleep(30)

    # Issuer did not get cred def id from initial create request, but it would have created asynchronously
    LOGGER.info("Trying to get cred def id")
    retry_count = 0
    retry_delay = 1
    max_retries = 30
    while retry_count < max_retries:
        try:
            get_cred_def_response = await issuer_client.get(
                f"{DEFINITIONS_BASE_PATH}/credentials"
            )
            get_cred_def_response.raise_for_status()
            LOGGER.info(f"Get cred def response: {get_cred_def_response.text}")
            break
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                pytest.fail(f"Failed to get cred def id after {max_retries} retries")

            LOGGER.info(f"Error getting cred def: {e}, retrying...")
            await asyncio.sleep(retry_delay)

    cred_def_list = get_cred_def_response.json()

    if not cred_def_list:
        pytest.fail("No cred defs found")

    cred_def_id = cred_def_list[0]["id"]

    # We can now call internal method to assert revocation registries are created
    LOGGER.info("Asserting revocation registries are successfully created")
    async with (
        get_tenant_acapy_client(token=get_token(issuer_client)) as issuer_acapy_client,
        asyncio.timeout(30),
    ):
        await wait_for_active_registry(issuer_acapy_client, cred_def_id)

    # Phase 1: Issue 1 credential to each holder
    LOGGER.info("Phase 1: Issuing credentials to all holders")
    credential_exchanges = []
    for i, (holder_client, connection_info) in enumerate(
        zip(holders, connections, strict=False)
    ):
        LOGGER.info(f"\tIssuing credential to holder {i}")
        cred_ex_record = await issue_single_credential(
            issuer_client=issuer_client,
            holder_client=holder_client,
            credential_definition_id=cred_def_id,
            connection=connection_info["faber_alice"],
            holder_index=i,
        )
        credential_exchanges.append(cred_ex_record)
        LOGGER.info(f"\tCredential issued to holder {i}")

    # Phase 2: Verify all holders (should be verified=True)
    LOGGER.info("Phase 2: Verifying all holders (credentials should be valid)")
    for i, (holder_client, connection_info) in enumerate(
        zip(holders, connections, strict=False)
    ):
        LOGGER.info(f"\tSending proof and asserting verified for holder {i}")
        await send_proof_and_assert_verified(
            verifier_client=issuer_client,
            holder_client=holder_client,
            bob_alice_connection=connection_info["bob_alice"],
            cred_def_id=cred_def_id,
            verified=True,
        )
        LOGGER.info(f"\tProof verified for holder {i}")

    # Phase 3: Revoke all credentials
    LOGGER.info("Phase 3: Revoking all credentials")
    for i, cred_ex_record in enumerate(credential_exchanges):
        LOGGER.info(f"\tRevoking credential for holder {i}")
        await revoke_single_credential(
            issuer_client=issuer_client,
            credential_exchange=cred_ex_record,
            auto_publish=True,
        )
        LOGGER.info(f"\tCredential revoked for holder {i}")

    LOGGER.info("Waiting 10 seconds for revocation to propagate")
    await asyncio.sleep(10)

    # Phase 4: Verify all holders again (should be verified=False after revocation)
    LOGGER.info("Phase 4: Verifying all holders (credentials should be revoked)")
    for i, (holder_client, connection_info) in enumerate(
        zip(holders, connections, strict=False)
    ):
        LOGGER.info(f"\tSending presentation request, asserting revoked for holder {i}")
        await send_proof_and_assert_verified(
            verifier_client=issuer_client,
            holder_client=holder_client,
            bob_alice_connection=connection_info["bob_alice"],
            cred_def_id=cred_def_id,
            verified=False,
        )
        LOGGER.info(f"\tPresentation request sent, credential revoked for holder {i}")

    LOGGER.info("All phases completed successfully")

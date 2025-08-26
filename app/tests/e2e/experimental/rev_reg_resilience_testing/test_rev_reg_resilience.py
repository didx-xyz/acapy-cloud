"""Testing revocation registry lifecycle management and recovery."""

import asyncio
import os
from dataclasses import dataclass

import pytest

from app.models.definitions import CreateCredentialDefinition, CredentialSchema
from app.models.tenants import CreateTenantResponse
from app.services.revocation_registry import wait_for_active_registry
from app.tests.e2e.experimental.rev_reg_resilience_testing.log_pattern_monitor import (
    LogPatternMonitor,
)
from app.tests.fixtures.definitions import (
    DEFINITIONS_BASE_PATH,
    fetch_or_create_regression_test_schema_definition,
)
from app.tests.fixtures.member_acapy_clients import get_token
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


@dataclass
class ResilienceTestScenario:
    """Configuration for a resilience test scenario."""

    name: str
    log_pattern: str
    description: str


# Define different resilience test scenarios
RESILIENCE_SCENARIOS = [
    ResilienceTestScenario(
        name="registry_definition_creation",
        log_pattern="Creating and registering revocation registry definition",
        description="Interrupt during revocation registry definition creation",
    ),
    ResilienceTestScenario(
        name="create_registry_definition_event",
        log_pattern="Emitting create revocation registry definition event",
        description="Interrupt when emitting create registry definition event",
    ),
    ResilienceTestScenario(
        name="registry_definition_publish",
        log_pattern="Publishing revocation registry definition resource",
        description="Interrupt during revocation registry definition publish",
    ),
    ResilienceTestScenario(
        name="tails_file_upload",
        log_pattern="Uploading tails file",
        description="Interrupt during tails file upload",
    ),
    ResilienceTestScenario(
        name="store_registry_definition_event",
        log_pattern="Emitting store revocation registry definition event",
        description="Interrupt when emitting store registry definition event",
    ),
    ResilienceTestScenario(
        name="handle_store_request",
        log_pattern="Handling registry store request",
        description="Interrupt while handling registry store request",
    ),
    ResilienceTestScenario(
        name="storing_registry_definition",
        log_pattern="Storing revocation registry definition",
        description="Interrupt while storing registry definition locally",
    ),
    ResilienceTestScenario(
        name="finishing_registry_definition",
        log_pattern="Emitting rev reg def finished event",
        description="Interrupt while emitting rev reg def finished event",
    ),
    ResilienceTestScenario(
        name="setting_active_registry",
        log_pattern="Setting registry as active",
        description="Interrupt while setting registry as active",
    ),
    ResilienceTestScenario(
        name="emitting_create_and_register_rev_list_event",
        log_pattern="Emitting create and register revocation list",
        description="Interrupt while emitting create and register revocation list",
    ),
    ResilienceTestScenario(
        name="storing_rev_list",
        log_pattern="Storing revocation registry list",
        description="Interrupt while storing revocation registry list",
    ),
]


async def setup_test_environment():
    """Set up the common test environment: schema, issuer, holders, and connections."""
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

    return schema_definition, issuer_client, holders, connections


async def run_resilience_scenario(
    scenario: ResilienceTestScenario,
    schema_definition: CredentialSchema,
    issuer_client: RichAsyncClient,
    holders: list[RichAsyncClient],
    connections: list[dict],
) -> None:
    """Run a single resilience test scenario."""
    LOGGER.info(f"=== Starting Resilience Scenario: {scenario.name} ===")
    LOGGER.info(f"Description: {scenario.description}")
    LOGGER.info(f"Log Pattern: {scenario.log_pattern}")

    # Start pod monitor-and-kill script for this scenario
    monitor = LogPatternMonitor(MONITOR_SCRIPT_PATH)
    monitor.start_monitoring(scenario.log_pattern)

    # Issuer creates credential definition (revocable)
    LOGGER.info("Creating credential definition")
    cred_def_tag = f"ResilienceTest_{scenario.name}_{random_string(5)}"
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

    if "storing_rev_list" in scenario.name:
        # Note: this may be sporadic. Should mostly be 200, but can be 500 too, depending on timing
        expected_status = 2  # 200
    else:
        expected_status = 5  # 500 or 503, since agent is killed while creating rev regs

    actual_status = create_cred_def_response.status_code // 100
    if actual_status != expected_status:
        LOGGER.warning(
            f"Expected {expected_status}xx for scenario {scenario.name}, got {create_cred_def_response.status_code}\n"
            "NB: mt-agent must run with debug logging enabled for the monitor_and_kill_pod.sh script to work\n"
            "Also, some of the scenarios may succeed if the interruption is after both rev regs are created"
        )

    monitor.stop_monitoring()

    # Agent should be restarting
    LOGGER.info("Waiting 20 seconds for agent to restart")
    await asyncio.sleep(20)

    # Issuer did not get cred def id from initial create request, but it would have created asynchronously
    LOGGER.info("Trying to get cred def id")
    retry_count = 0
    retry_delay = 1
    max_retries = 30
    cred_def_id = None

    while retry_count < max_retries:
        try:
            get_cred_def_response = await issuer_client.get(
                f"{DEFINITIONS_BASE_PATH}/credentials"
            )
            get_cred_def_response.raise_for_status()
            LOGGER.info(f"Get cred def response: {get_cred_def_response.text}")

            cred_def_list: list[dict] = get_cred_def_response.json()
            # Find the credential definition we just created by tag
            for cred_def in cred_def_list:
                LOGGER.info(f"Cred def: {cred_def}")
                LOGGER.info(f"Cred def tag: {cred_def['tag']}")
                if cred_def["tag"] == cred_def_tag:
                    cred_def_id = cred_def["id"]
                    LOGGER.info(f"✅ Found matching cred def with ID: {cred_def_id}")
                    break

            if cred_def_id:
                # Successfully found the credential definition, exit retry loop
                break
            else:
                LOGGER.info(
                    f"No matching cred def found for tag: {cred_def_tag}, retrying..."
                )

        except Exception as e:
            LOGGER.info(f"Error getting cred def: {e}, retrying...")

        retry_count += 1
        if retry_count == max_retries:
            pytest.fail(
                f"Failed to get cred def id after {max_retries} retries for scenario {scenario.name}"
            )
        await asyncio.sleep(retry_delay)

    if not cred_def_id:
        pytest.fail(f"No matching cred def found for scenario {scenario.name}")

    # We can now call internal method to assert revocation registries are created
    LOGGER.info("Asserting revocation registries are successfully created")
    async with (
        get_tenant_acapy_client(token=get_token(issuer_client)) as issuer_acapy_client,
        asyncio.timeout(30),
    ):
        await wait_for_active_registry(issuer_acapy_client, cred_def_id)

    LOGGER.info("Waiting additional 15 seconds to ensure rev reg is created")
    await asyncio.sleep(15)

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

    LOGGER.info(f"=== Scenario {scenario.name} completed successfully ===")


@pytest.mark.anyio
@pytest.mark.skip(reason="Test is for local testing only")
async def test_rev_reg_resilience():
    """Test revocation registry resilience across multiple scenarios."""
    LOGGER.info("=== Starting Revocation Registry Resilience Test Suite ===")

    # Set up common test environment once
    (
        schema_definition,
        issuer_client,
        holders,
        connections,
    ) = await setup_test_environment()

    # Run each resilience scenario
    for i, scenario in enumerate(RESILIENCE_SCENARIOS):
        LOGGER.info(
            f"Running scenario {i + 1}/{len(RESILIENCE_SCENARIOS)}: {scenario.name}"
        )

        try:
            await run_resilience_scenario(
                scenario=scenario,
                schema_definition=schema_definition,
                issuer_client=issuer_client,
                holders=holders,
                connections=connections,
            )
            LOGGER.info(f"✅ Scenario {scenario.name} passed")

        except Exception as e:
            LOGGER.error(f"❌ Scenario {scenario.name} failed: {e!s}")
            # Continue with other scenarios even if one fails
            continue

        # Brief pause between scenarios
        LOGGER.info("Waiting 5 seconds before next scenario")
        await asyncio.sleep(5)

    LOGGER.info("=== All resilience scenarios completed ===")

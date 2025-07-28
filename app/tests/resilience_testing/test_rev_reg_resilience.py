"""Testing revocation registry lifecycle management and recovery."""

import asyncio
import time

import pytest

from app.models.definitions import CreateCredentialDefinition
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
from app.tests.util.regression_testing import get_or_create_tenant
from app.tests.util.verifier import VERIFIER_BASE_PATH, send_proof_request
from app.tests.util.webhooks import assert_both_webhooks_received, check_webhook_state
from app.util.string import random_string
from shared.log_config import get_logger
from shared.models.credential_exchange import CredentialExchange
from shared.util.rich_async_client import RichAsyncClient

MONITOR_SCRIPT_PATH = "./app/tests/resilience_testing/monitor_and_kill_pod.sh"
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
        holder_tenant = await get_or_create_tenant(
            admin_client=admin_client, name=holder_name, roles=[]
        )
        holder_client = get_tenant_client(
            token=holder_tenant.access_token, name=f"Holder{i}"
        )
        holders.append(holder_client)
        LOGGER.info(f"\tHolder {i} tenant created: {holder_name}")

        # Create connection between issuer and this holder
        await asyncio.sleep(1.5)
        connection_alias = f"ResilienceTestConnection{i}_" + random_string(5)
        bob_alice_connection = await create_bob_alice_connection(
            alice_member_client=holder_client,
            bob_member_client=issuer_client,
            alias=connection_alias,
        )
        faber_alice_connection = FaberAliceConnect(
            alice_connection_id=bob_alice_connection.alice_connection_id,
            faber_connection_id=bob_alice_connection.bob_connection_id,
        )
        connections.append(
            {"bob_alice": bob_alice_connection, "faber_alice": faber_alice_connection}
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


async def issue_single_credential(
    issuer_client: RichAsyncClient,
    holder_client: RichAsyncClient,
    credential_definition_id: str,
    connection: FaberAliceConnect,
    holder_index: int,
) -> CredentialExchange:
    """Issue a single credential to a holder and wait for completion."""
    # Issue credential
    credential = {
        "connection_id": connection.faber_connection_id,
        "save_exchange_record": True,
        "anoncreds_credential_detail": {
            "credential_definition_id": credential_definition_id,
            "attributes": {"speed": str(holder_index), "name": "Alice", "age": "44"},
        },
    }

    issuer_cred_ex_id = (
        await issuer_client.post(
            CREDENTIALS_BASE_PATH,
            json=credential,
        )
    ).json()["credential_exchange_id"]

    # Wait for holder to receive the credential offer
    num_tries = 0
    holder_cred_ex = None
    while holder_cred_ex is None and num_tries < 10:
        await asyncio.sleep(0.25)
        holder_cred_ex_response = (
            await holder_client.get(
                f"{CREDENTIALS_BASE_PATH}?connection_id={connection.alice_connection_id}"
            )
        ).json()
        if holder_cred_ex_response:
            holder_cred_ex = holder_cred_ex_response[0]
        num_tries += 1

    if holder_cred_ex is None:
        pytest.fail(f"Holder {holder_index} did not receive credential offer")

    cred_ex_id = holder_cred_ex["credential_exchange_id"]

    # Holder requests the credential
    await holder_client.post(
        f"{CREDENTIALS_BASE_PATH}/{cred_ex_id}/request?save_exchange_record=true",
        json={},
    )

    # Wait for credential state "done"
    await check_webhook_state(
        client=holder_client,
        topic="credentials",
        state="done",
        filter_map={
            "credential_exchange_id": cred_ex_id,
        },
    )

    # Get the final credential exchange record from issuer
    issuer_cred_ex_response = (
        await issuer_client.get(f"{CREDENTIALS_BASE_PATH}/{issuer_cred_ex_id}")
    ).json()

    return CredentialExchange(**issuer_cred_ex_response)


async def revoke_single_credential(
    issuer_client: RichAsyncClient,
    credential_exchange: CredentialExchange,
    auto_publish: bool = True,
) -> None:
    """Revoke a single credential."""
    await issuer_client.post(
        f"{CREDENTIALS_BASE_PATH}/revoke",
        json={
            "credential_exchange_id": credential_exchange.credential_exchange_id,
            "auto_publish_on_ledger": auto_publish,
        },
    )


async def send_proof_and_assert_verified(
    verifier_client: RichAsyncClient,
    holder_client: RichAsyncClient,
    bob_alice_connection: BobAliceConnect,
    cred_def_id: str,
    verified: bool,
):
    # Do proof request
    request_body = {
        "comment": "Test proof of revocation",
        "anoncreds_proof_request": {
            "name": "Proof of SPEED",
            "version": "1.0",
            "non_revoked": {"to": int(time.time())},
            "requested_attributes": {
                "THE_SPEED": {
                    "name": "speed",
                    "restrictions": [{"cred_def_id": cred_def_id}],
                }
            },
            "requested_predicates": {},
        },
        "save_exchange_record": True,
        "connection_id": bob_alice_connection.bob_connection_id,
    }
    send_proof_response = await send_proof_request(verifier_client, request_body)
    acme_proof_exchange_id = send_proof_response["proof_id"]

    alice_payload = await check_webhook_state(
        client=holder_client,
        topic="proofs",
        state="request-received",
        filter_map={
            "thread_id": send_proof_response["thread_id"],
        },
    )

    alice_proof_exchange_id = alice_payload["proof_id"]

    # Get referent -- retry loop because sometimes the credentials don't show up
    retry_count = 0
    max_retries = 10
    while retry_count < max_retries:
        creds = (
            await holder_client.get(
                f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_exchange_id}/credentials"
            )
        ).json()
        if creds:
            break

        retry_count += 1
        if retry_count == max_retries:
            pytest.fail(f"No credentials found for proof {alice_proof_exchange_id}")
        await asyncio.sleep(1)

    referent = creds[0]["cred_info"]["credential_id"]

    # Send proof
    await holder_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json={
            "proof_id": alice_proof_exchange_id,
            "anoncreds_presentation_spec": {
                "requested_attributes": {
                    "THE_SPEED": {"cred_id": referent, "revealed": True}
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
        },
    )

    await assert_both_webhooks_received(
        holder_client,
        verifier_client,
        "proofs",
        "done",
        alice_proof_exchange_id,
        acme_proof_exchange_id,
    )

    # Check proof
    proof = (
        await verifier_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{acme_proof_exchange_id}"
        )
    ).json()

    assert proof["verified"] is verified

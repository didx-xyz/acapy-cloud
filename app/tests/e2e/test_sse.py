import asyncio

import pytest

from app.models.tenants import CreateTenantResponse
from app.routes.sse import router
from app.tests.util.connections import create_bob_alice_connection
from shared import RichAsyncClient

SSE_PATH = router.prefix


async def get_event_data(
    client: RichAsyncClient,
    wallet_id: str,
    alias: str,
) -> dict:
    """Helper function to get event data from SSE."""
    url = f"{SSE_PATH}/{wallet_id}/connections/alias/{alias}/completed"

    async with client.stream("GET", url) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                return data
            elif line == "" or line.startswith(": ping"):
                continue
            elif "upstream connect error" in line:
                pytest.fail(f"Connection error detected in SSE stream: {line}")

    pytest.fail("No data received from SSE stream.")


@pytest.mark.anyio
async def test_sse(
    bob_member_client: RichAsyncClient,
    bob_tenant: CreateTenantResponse,
    alice_member_client: RichAsyncClient,
):
    connection_tasks = []
    for i in range(100):
        task = create_bob_alice_connection(
            bob_member_client, alice_member_client, f"test_sse_{i}"
        )
        connection_tasks.append(task)

    await asyncio.gather(*connection_tasks)

    wallet_id = bob_tenant.wallet_id
    sse_tasks = []
    for i in range(100):
        task = get_event_data(bob_member_client, wallet_id, f"test_sse_{i}")
        sse_tasks.append(task)

    results = await asyncio.gather(*sse_tasks)
    for result in results:
        assert result, "No event data received from SSE stream"

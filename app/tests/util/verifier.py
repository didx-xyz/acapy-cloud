from typing import Any

from app.routes.verifier import router as verifier_router
from shared.util.rich_async_client import RichAsyncClient

VERIFIER_BASE_PATH = verifier_router.prefix


async def send_proof_request(client: RichAsyncClient, json_body: dict[str, Any]):
    response = await client.post(
        VERIFIER_BASE_PATH + "/send-request",
        json=json_body,
    )
    return response.json()

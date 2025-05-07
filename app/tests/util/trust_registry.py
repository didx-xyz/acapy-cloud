from contextlib import asynccontextmanager
from random import random
from typing import AsyncGenerator

from app.routes.wallet.dids import router as wallet_router
from app.services.trust_registry.actors import register_actor, remove_actor_by_id
from shared import RichAsyncClient
from shared.models.trustregistry import Actor

WALLET_BASE_PATH = wallet_router.prefix


@asynccontextmanager
async def register_issuer_key(
    faber_client: RichAsyncClient, key_type: str
) -> AsyncGenerator[str, None]:
    did_create_options = {"method": "key", "key_type": key_type}

    wallet_response = (
        await faber_client.post(WALLET_BASE_PATH, json=did_create_options)
    ).json()
    did = wallet_response["did"]

    rand = random()
    test_id = f"test-actor-{rand}"

    await register_actor(
        Actor(
            id=test_id,
            name=f"Test Actor-{rand}",
            roles=["issuer"],
            did=did,
            didcomm_invitation=None,
        )
    )

    try:
        yield did
    finally:
        await remove_actor_by_id(test_id)

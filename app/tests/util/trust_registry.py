from httpx import AsyncClient
from random import random

from app.facades.trust_registry import (
    Actor,
    actor_by_did,
    register_actor,
    register_schema,
    registry_has_schema,
)


async def register_issuer(client: AsyncClient, schema_id: str):
    pub_did_res = await client.get("/wallet/fetch-current-did")
    pub_did = pub_did_res.json()["result"]["did"]

    if not await registry_has_schema(schema_id=schema_id):
        await register_schema(schema_id)

    if not await actor_by_did(f"did:sov:{pub_did}"):
        rand = random()
        await register_actor(
            Actor(
                id=f"test-actor-{rand}",
                name=f"Test Actor-{rand}",
                roles=["issuer", "verifier"],
                did=f"did:sov:{pub_did}",
                didcomm_invitation=None,
            )
        )

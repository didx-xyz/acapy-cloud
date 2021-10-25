import logging
import os
from fastapi.exceptions import HTTPException
import requests
from typing import List, Literal


TRUST_REGISTRY_URL = os.getenv("TRUST_REGISTRY_URL", "http://localhost:8001/")

logger = logging.getLogger(__name__)

Role = Literal["issuer", "verifier"]


async def actor_has_role(actor_id: str, role: Role) -> bool:
    actor_res = requests.get(TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}")
    if actor_res.status_code != 200:
        raise HTTPException(404, detail="Actor does not exist")
    return bool(role in actor_res.json()["roles"])


async def actors_with_role(role: str = Role) -> list:
    actors = requests.get(TRUST_REGISTRY_URL + "/registry/actors")
    if actors.status_code != 200:
        return []
    actors_with_role_list = [
        actor for actor in actors.json()["actors"] if role in actor["roles"]
    ]
    return actors_with_role_list


async def actor_has_schema(actor_id: str, schema_id: str) -> bool:
    actor_res = requests.get(TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}")
    if actor_res.status_code != 200:
        return False
    return bool(schema_id in actor_res.json()["schemas"])


async def registry_has_schema(schema_id: str) -> bool:
    schema_res = requests.get(TRUST_REGISTRY_URL + "/registry/schemas")
    if schema_res.status_code != 200:
        return False
    return bool(schema_id in schema_res.json()["schemas"])


async def get_did_for_actor(actor_id: str) -> List[str]:
    actor_res = requests.get(TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}")
    if actor_res.status_code != 200:
        return None
    did = actor_res.json()["did"]
    didcomm_invitation = actor_res.json()["didcomm_invitation"]
    return [did, didcomm_invitation]

import logging
import os
from typing import Literal, Union, List
from fastapi.exceptions import HTTPException

import requests

TRUST_REGISTRY_URL = os.getenv("TRUST_REGISTRY_URL", "http://localhost:8001/")

logger = logging.getLogger(__name__)


async def actor_has_role(
    actor_id: str, role: str = Union[Literal["issuer"], Literal["verifier"]]
) -> bool:
    actor_res = requests.get(TRUST_REGISTRY_URL + f"/registry/actors/{actor_id}")
    if actor_res.status_code != 200:
        raise HTTPException(404, detail="Actor does not exist")
    return bool(role in actor_res.json()["roles"])


async def actors_with_role(
    role: str = Union[Literal["issuer"], Literal["verifier"]]
) -> list:
    actors = requests.get(TRUST_REGISTRY_URL + "/registry/actors")
    actors_with_role_list = []
    if actors.status_code != 200:
        return actors_with_role_list
    [
        actors_with_role_list.append(actor)
        for actor in actors.json()["actors"]
        if role in actor["roles"]
    ]
    return actors_with_role_list


async def actor_has_schema(actor_id: str, schema_id: str) -> False:
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

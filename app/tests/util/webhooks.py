import time
from typing import Dict, List, Optional

from httpx import AsyncClient
import httpx
from pydantic import BaseModel

from app.facades.webhooks import get_wallet_id_from_b64encoded_jwt, topics
from app.tests.util.constants import WEBHOOKS_URL


class FilterMap(BaseModel):
    filter_key: str
    filter_value: str


def get_wallet_id_from_async_client(client: AsyncClient) -> str:
    is_non_jwt = len(client.headers.get("x-api-key").split(".")) == 2

    if is_non_jwt:
        return "admin"

    # eg tenenat_jwt: "eyJ3YWxsZXRfaWQiOiIwMzg4OTc0MC1iNDg4LTRmZjEtYWI4Ni0yOTM0NzQwZjNjNWMifQ"
    jwt = client.headers.get("x-api-key").split(".")[2]
    return get_wallet_id_from_b64encoded_jwt(jwt)


def check_webhook_state(
    client: AsyncClient,
    topic: topics,
    filter_map: Dict[str, Optional[str]] = {},
    max_duration: int = 15,
    poll_interval: int = 1,
) -> bool:
    assert poll_interval >= 0, "Poll interval cannot be negative"
    assert max_duration >= 0, "Poll duration cannot be negative"

    wallet_id = get_wallet_id_from_async_client(client)

    t_end = time.time() + max_duration
    while time.time() < t_end:
        hooks = httpx.get(f"{WEBHOOKS_URL}/{topic}/{wallet_id}").json()

        # Loop through all hooks
        for hook in hooks:
            payload = hook["payload"]
            # Find the right hook
            match = all(
                payload.get(filter_key, None) == filter_value
                for filter_key, filter_value in filter_map.items()
            )

            if match:
                return True

        time.sleep(poll_interval)
    raise Exception(f"Cannot satisfy webhook filter \n{filter_map}\n. Found \n{hooks}")


def get_hooks_per_topic_per_wallet(client: AsyncClient, topic: topics) -> List:
    wallet_id = get_wallet_id_from_async_client(client)
    try:
        hooks = (httpx.get(f"{WEBHOOKS_URL}/{topic}/{wallet_id}")).json()
        return hooks if hooks else []
    except httpx.HTTPError as e:
        raise e from e

import asyncio
from typing import Any

import pytest
from httpx import HTTPError

from app.tests.util.sse_listener import SseListener, SseListenerTimeoutError
from app.util.tenants import get_wallet_id_from_b64encoded_jwt
from shared import RichAsyncClient
from shared.log_config import get_logger
from shared.models.webhook_events import CloudApiTopics

logger = get_logger(__name__)


def get_wallet_id_from_async_client(client: RichAsyncClient) -> str:
    is_non_jwt = len(client.headers.get("x-api-key").split(".")) == 2

    if is_non_jwt:
        return "admin"

    # eg tenant_jwt: "eyJ3YWxsZXRfaWQiOiIwMzg4OTc0MC1iNDg4LTRmZjEtYWI4Ni0yOTM0NzQwZjNjNWMifQ"
    jwt = client.headers.get("x-api-key").split(".")[2]
    return get_wallet_id_from_b64encoded_jwt(jwt)


async def check_webhook_state(
    client: RichAsyncClient,
    topic: CloudApiTopics,
    state: str,
    filter_map: dict[str, str] | None = None,
    max_duration: int = 45,
    max_tries: int = 2,
    delay: float = 0.5,
    look_back: int = 15,
) -> dict[str, Any]:
    assert max_duration >= 0, "Poll duration cannot be negative"

    wallet_id = get_wallet_id_from_async_client(client)

    listener = SseListener(wallet_id, topic)
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "topic": topic})

    # Retry logic in case of disconnect errors (don't retry on timeout errors)
    event = None
    attempt = 0

    while not event and attempt < max_tries:
        try:
            if filter_map:
                # Assuming that filter_map contains 1 key-value pair
                field, field_id = next(iter(filter_map.items()))

                bound_logger.info(
                    "Waiting for event with field:field_id {}:{}, and state {}",
                    field,
                    field_id,
                    state,
                )
                event = await listener.wait_for_event(
                    field=field,
                    field_id=field_id,
                    desired_state=state,
                    timeout=max_duration,
                    look_back=look_back,
                )
            else:
                pytest.fail(
                    "No longer implemented: cannot wait for event without filter_map"
                )
        except SseListenerTimeoutError:
            bound_logger.error(
                "Encountered SSE Timeout (server didn't return expected event in time)."
            )
            raise
        except HTTPError as e:
            if attempt + 1 >= max_tries:
                bound_logger.error(
                    "Encountered {} HTTPErrors while waiting for SSE event. Failing",
                    max_tries,
                )
                raise
            else:
                bound_logger.warning(
                    "Attempt {}. Encountered HTTP Error while waiting for SSE Event: {}.",
                    attempt + 1,
                    e,
                )

        if not event:
            attempt += 1
            bound_logger.warning("Retrying SSE request in {}s", delay)
            await asyncio.sleep(delay)

    if event:
        return event
    else:
        pytest.fail(f"Could not satisfy webhook filter: `{filter_map}`.")


# mapping of topics to their relevant field names
TOPIC_FIELD_MAP = {
    "connections": "connection_id",
    "proofs": "proof_id",
    "credentials": "credential_exchange_id",
}


async def assert_both_webhooks_received(
    member_client_1: RichAsyncClient,
    member_client_2: RichAsyncClient,
    topic: str,
    state: str,
    field_id_1: str,
    field_id_2: str,
) -> None:
    # Lookup the field name for the given topic
    field_name = TOPIC_FIELD_MAP.get(topic)
    if not field_name:
        raise ValueError(f"Unsupported topic: {topic}")

    async def check_webhook(client, field_id) -> dict[str, Any]:
        return await check_webhook_state(
            client, topic=topic, state=state, filter_map={field_name: field_id}
        )

    results = await asyncio.gather(
        check_webhook(member_client_1, field_id_1),
        check_webhook(member_client_2, field_id_2),
    )

    assert all(results), "Not all webhooks received the expected state"

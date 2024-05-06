import asyncio
from typing import Any, Dict, Optional

from httpx import HTTPError

from app.tests.util.sse_listener import SseListener, SseListenerTimeout
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
    filter_map: Optional[Dict[str, str]] = None,
    max_duration: int = 30,
    look_back: float = 1,
    max_tries: int = 2,
    delay: float = 0.5,
) -> Dict[str, Any]:
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
                field, field_id = list(filter_map.items())[0]

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
                    look_back=look_back + attempt * max_duration,  # scale per attempt
                )
            else:
                bound_logger.info("Waiting for event with state {}", state)
                event = await listener.wait_for_state(
                    desired_state=state,
                    timeout=max_duration,
                    look_back=look_back + attempt * max_duration,  # scale per attempt
                )
        except SseListenerTimeout:
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
        raise Exception(f"Could not satisfy webhook filter: `{filter_map}`.")

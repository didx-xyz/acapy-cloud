from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from httpx import HTTPError, Response, Timeout

from shared.constants import WAYPOINT_URL
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)
SSE_PING_PERIOD = 15
# SSE sends a ping every 15 seconds, so user will get at least one message within this timeout
default_timeout = Timeout(SSE_PING_PERIOD, read=3600.0)  # 1 hour read timeout
event_timeout = Timeout(SSE_PING_PERIOD, read=180)  # 3 minute timeout


async def yield_lines_with_disconnect_check(
    request: Request, response: Response
) -> AsyncGenerator[str, None]:
    async for line in response.aiter_lines():
        if await request.is_disconnected():
            logger.bind(body=request).debug("SSE Client disconnected.")
            break  # Client has disconnected, stop sending events
        yield line + "\n"


async def sse_subscribe_event_with_field_and_state(
    *,
    request: Request,
    group_id: str | None,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    look_back: int = 60,
) -> AsyncGenerator[str, None]:
    """Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        request: The request object.
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        field: The field of interest that field_id will match on (e.g. connection_id, thread_id, etc).
        field_id: The identifier of the field that the webhook event will match on.
        desired_state: The state that the webhook event will match on.
        look_back: The number of seconds to look back for events before subscribing.

    Returns:
        AsyncGenerator[str, None]: A generator that yields the events.

    """
    bound_logger = logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
            "state": desired_state,
        }
    )

    params: dict[str, Any] = {}
    if group_id:  # Optional params
        params["group_id"] = group_id
    if look_back:
        params["look_back"] = look_back

    try:
        async with RichAsyncClient(timeout=event_timeout) as client:
            bound_logger.debug(
                "Connecting stream to /sse/wallet_id/topic/field/field_id/desired_state"
            )
            async with client.stream(
                "GET",
                f"{WAYPOINT_URL}/sse/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
                params=params,
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e

from typing import AsyncGenerator, Optional

from fastapi import Request
from httpx import HTTPError, Response, Timeout

from shared import WEBHOOKS_URL
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


async def sse_subscribe_wallet(
    *, request: Request, group_id: Optional[str], wallet_id: str
) -> AsyncGenerator[str, None]:
    """
    Subscribe to server-side events for a specific wallet ID.

    Args:
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
    """
    bound_logger = logger.bind(body={"group_id": group_id, "wallet_id": wallet_id})
    params = {"group_id": group_id} if group_id else None
    try:
        async with RichAsyncClient(timeout=default_timeout) as client:
            bound_logger.debug("Connecting stream to /sse/wallet_id")
            async with client.stream(
                "GET", f"{WEBHOOKS_URL}/sse/{wallet_id}", params=params
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e


async def sse_subscribe_wallet_topic(
    *, request: Request, group_id: Optional[str], wallet_id: str, topic: str
) -> AsyncGenerator[str, None]:
    """
    Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
    """
    bound_logger = logger.bind(
        body={"group_id": group_id, "wallet_id": wallet_id, "topic": topic}
    )
    params = {"group_id": group_id} if group_id else None
    try:
        async with RichAsyncClient(timeout=default_timeout) as client:
            bound_logger.debug("Connecting stream to /sse/wallet_id/topic")
            async with client.stream(
                "GET", f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}", params=params
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e


async def sse_subscribe_event_with_state(
    *,
    request: Request,
    group_id: Optional[str],
    wallet_id: str,
    topic: str,
    desired_state: str,
) -> AsyncGenerator[str, None]:
    """
    Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        desired_state: The state that the webhook event will match on.
    """
    bound_logger = logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            "state": desired_state,
        }
    )
    params = {"group_id": group_id} if group_id else None
    try:
        async with RichAsyncClient(timeout=event_timeout) as client:
            bound_logger.debug(
                "Connecting stream to /sse/wallet_id/topic/desired_state"
            )
            async with client.stream(
                "GET",
                f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{desired_state}",
                params=params,
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e


async def sse_subscribe_stream_with_fields(
    *,
    request: Request,
    group_id: Optional[str],
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
) -> AsyncGenerator[str, None]:
    """
    Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        field: The field of interest that field_id will match on (e.g. connection_id, thread_id, etc).
        field_id: The identifier of the field that will be filtered for.
    """
    bound_logger = logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
        }
    )
    params = {"group_id": group_id} if group_id else None
    try:
        async with RichAsyncClient(timeout=default_timeout) as client:
            bound_logger.debug(
                "Connecting stream to /sse/wallet_id/topic/field/field_id"
            )
            async with client.stream(
                "GET",
                f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{field}/{field_id}",
                params=params,
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e


async def sse_subscribe_event_with_field_and_state(
    *,
    request: Request,
    group_id: Optional[str],
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
) -> AsyncGenerator[str, None]:
    """
    Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        group_id: The group to which the wallet belongs.
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        field: The field of interest that field_id will match on (e.g. connection_id, thread_id, etc).
        field_id: The identifier of the field that the webhook event will match on.
        desired_state: The state that the webhook event will match on.
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
    params = {"group_id": group_id} if group_id else None
    try:
        async with RichAsyncClient(timeout=event_timeout) as client:
            bound_logger.debug(
                "Connecting stream to /sse/wallet_id/topic/field/field_id/desired_state"
            )
            async with client.stream(
                "GET",
                f"{WEBHOOKS_URL}/sse/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
                params=params,
            ) as response:
                async for line in yield_lines_with_disconnect_check(request, response):
                    yield line
    except HTTPError as e:
        bound_logger.error("Caught HTTPError while handling SSE subscription: {}.", e)
        raise e

import asyncio
import logging
import time
from typing import Any, Generator

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Request
from sse_starlette.sse import EventSourceResponse

from shared import WEBHOOK_TOPIC_ALL, APIRouter
from webhooks.dependencies.container import Container
from webhooks.dependencies.sse_manager import SseManager

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sse",
    tags=["sse"],
)

SSE_TIMEOUT = 150  # maximum duration of an SSE connection
queue_poll_period = 0.1  # period in seconds to retry reading empty queues


@router.get(
    "/{wallet_id}",
    response_class=EventSourceResponse,
    summary="Subscribe to wallet ID server-side events",
)
@inject
async def sse_subscribe_wallet(
    request: Request,
    wallet_id: str,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    """
    Subscribe to server-side events for a specific wallet ID.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        sse_manager: The SSEManager instance managing the server-sent events.
    """

    async def event_stream() -> Generator[str, Any, None]:
        async with sse_manager.sse_event_stream(
            wallet_id, WEBHOOK_TOPIC_ALL, duration=2  # So far only used in tests
        ) as event_generator:
            async for event in event_generator:
                if await request.is_disconnected():
                    LOGGER.debug("SSE event_stream: client disconnected")
                    break
                try:
                    yield event.json()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(queue_poll_period)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    LOGGER.debug("SSE event_stream closing with CancelledError")
                    break

    return EventSourceResponse(event_stream())


@router.get(
    "/{wallet_id}/{topic}",
    response_class=EventSourceResponse,
    summary="Subscribe to topic and wallet ID server-side events",
)
@inject
async def sse_subscribe_wallet_topic(
    request: Request,
    wallet_id: str,
    topic: str,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    """
    Subscribe to server-side events for a specific topic and wallet ID.

    Args:
        topic: The topic to which the wallet is subscribing.
        wallet_id: The ID of the wallet subscribing to the events.
        sse_manager: The SSEManager instance managing the server-sent events.
    """

    async def event_stream() -> Generator[str, Any, None]:
        async with sse_manager.sse_event_stream(
            wallet_id, topic, duration=2  # So far only used in tests
        ) as event_generator:
            async for event in event_generator:
                if await request.is_disconnected():
                    LOGGER.debug("SSE event_stream: client disconnected")
                    break
                try:
                    event: TopicItem = queue.get_nowait()
                    yield event.json()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(queue_poll_period)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    break

    return EventSourceResponse(event_stream())


@router.get(
    "/{wallet_id}/{topic}/{desired_state}",
    response_class=EventSourceResponse,
    summary="Wait for a desired state to be reached for some event for this wallet and topic "
    "`desired_state` may be `offer-received`, `transaction-acked`, `done`, etc.",
)
@inject
async def sse_subscribe_desired_state(
    request: Request,
    wallet_id: str,
    topic: str,
    desired_state: str,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    # Special case: Endorsements only contain two fields: `state` and `transaction_id`.
    # Endorsement Listeners will query by state only, in order to get the relevant transaction id.
    # So, a problem arises because the Admin wallet can listen for "request-received",
    # and we may return transaction_ids matching that state, but they have already been endorsed.
    # So, instead of imposing an arbitrary sleep duration for the listeners, for the event to arrive,
    # we will instead only return endorsement records if their state in cache isn't also acked or endorsed
    # Therefore, before sending events, we will check the state, and use an ignore list, as follows.

    async def event_stream():
        ignore_list = []
        async with sse_manager.sse_event_stream(
            wallet_id, topic, SSE_TIMEOUT
        ) as event_generator:
            async for event in event_generator:
                if await request.is_disconnected():
                    LOGGER.debug("SSE event_stream: client disconnected")
                    break
                try:
                    payload = dict(event.payload)  # to check if keys exist in payload

                    if topic == "endorsements" and desired_state == "request-received":
                        if (
                            payload["state"]
                            in ["transaction-acked", "transaction-endorsed"]
                            and payload["transaction_id"] not in ignore_list
                        ):
                            ignore_list += (payload["transaction_id"],)
                            continue
                        if payload["transaction_id"] in ignore_list:
                            continue

                    if "state" in payload and payload["state"] == desired_state:
                        yield event.json()  # Send the event
                        break  # End the generator
                except asyncio.QueueEmpty:
                    await asyncio.sleep(queue_poll_period)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    break

    return EventSourceResponse(event_stream())


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
    response_class=EventSourceResponse,
    summary="Wait for a desired state to be reached for some event for this wallet and topic "
    "The `relevant_id` refers to a `transaction_id` when using topic `endorsements,"
    "or a `connection_id` on topics: `connections`, `credentials`, or `proofs`, etc."
    "`desired_state` may be `offer-received`, `transaction-acked`, `done`, etc.",
)
@inject
async def sse_subscribe_filtered_event(
    request: Request,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    async def event_stream():
        async with sse_manager.sse_event_stream(
            wallet_id, topic, SSE_TIMEOUT
        ) as event_generator:
            async for event in event_generator:
                if await request.is_disconnected():
                    LOGGER.debug("SSE event_stream: client disconnected")
                    break
                try:
                    payload = dict(event.payload)  # to check if keys exist in payload
                    if (
                        field in payload
                        and payload[field] == field_id
                        and payload["state"] == desired_state
                    ):
                        yield event.json()  # Send the event
                        break  # End the generator
                except asyncio.QueueEmpty:
                    await asyncio.sleep(queue_poll_period)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    break

    return EventSourceResponse(event_stream())

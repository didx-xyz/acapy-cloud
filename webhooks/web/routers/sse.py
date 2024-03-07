import asyncio
from typing import Any, Generator

from dependency_injector.wiring import Provide, inject
from fastapi import BackgroundTasks, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from shared import DISCONNECT_CHECK_PERIOD, QUEUE_POLL_PERIOD, SSE_TIMEOUT, APIRouter
from shared.constants import MAX_EVENT_AGE_SECONDS
from shared.log_config import get_logger
from shared.models.webhook_events import WEBHOOK_TOPIC_ALL
from webhooks.services.dependency_injection.container import Container
from webhooks.services.sse_manager import SseManager
from webhooks.util.event_generator_wrapper import EventGeneratorWrapper

logger = get_logger(__name__)

router = APIRouter(
    prefix="/sse",
    tags=["sse"],
)

lookback_time_field = Query(
    default=MAX_EVENT_AGE_SECONDS,
    description=(
        "Duration in seconds to lookback in time to include past events "
        f"(default is the max event age stored in SSE: {MAX_EVENT_AGE_SECONDS} seconds). "
        "Setting to 0 means only events after connection is established will be returned"
    ),
)


async def check_disconnection(request: Request, stop_event: asyncio.Event):
    while not stop_event.is_set():
        if await request.is_disconnected():
            logger.debug("SSE check_disconnection: request has disconnected.")
            stop_event.set()
        await asyncio.sleep(DISCONNECT_CHECK_PERIOD)


@router.get(
    "/{wallet_id}",
    response_class=EventSourceResponse,
    summary="Subscribe to wallet ID server-side events",
)
@inject
async def sse_subscribe_wallet(
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    lookback_time: int = lookback_time_field,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    """
    Subscribe to server-side events for a specific wallet ID.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        sse_manager: The SSEManager instance managing the server-sent events.
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.info(
        "SSE: GET request received: Subscribe to wallet events on all topics"
    )

    async def event_stream() -> Generator[str, Any, None]:
        stop_event = asyncio.Event()
        event_generator_wrapper: EventGeneratorWrapper = (
            await sse_manager.sse_event_stream(
                wallet=wallet_id,
                topic=WEBHOOK_TOPIC_ALL,
                lookback_time=lookback_time,
                stop_event=stop_event,
            )
        )
        async with event_generator_wrapper as event_generator:
            background_tasks.add_task(check_disconnection, request, stop_event)

            async for event in event_generator:
                if await request.is_disconnected():
                    bound_logger.info("SSE event_stream: client disconnected.")
                    stop_event.set()
                    break
                try:
                    result = event.model_dump_json()
                    bound_logger.trace("Yielding SSE event: {}", result)
                    yield result
                except asyncio.QueueEmpty:
                    await asyncio.sleep(QUEUE_POLL_PERIOD)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    bound_logger.info("SSE event stream cancelled.")
                    stop_event.set()
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
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    lookback_time: int = lookback_time_field,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    """
    Subscribe to server-side events for a specific topic and wallet ID.

    Args:
        topic: The topic to which the wallet is subscribing.
        wallet_id: The ID of the wallet subscribing to the events.
        sse_manager: The SSEManager instance managing the server-sent events.
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "topic": topic})
    bound_logger.info("SSE: GET request received: Subscribe to wallet events by topic")

    async def event_stream() -> Generator[str, Any, None]:
        stop_event = asyncio.Event()
        event_generator_wrapper: EventGeneratorWrapper = (
            await sse_manager.sse_event_stream(
                wallet=wallet_id,
                topic=topic,
                lookback_time=lookback_time,
                stop_event=stop_event,
            )
        )
        async with event_generator_wrapper as event_generator:
            background_tasks.add_task(check_disconnection, request, stop_event)

            async for event in event_generator:
                if await request.is_disconnected():
                    bound_logger.info("SSE event_stream: client disconnected.")
                    stop_event.set()
                    break
                try:
                    result = event.model_dump_json()
                    bound_logger.trace("Yielding SSE event: {}", result)
                    yield result
                except asyncio.QueueEmpty:
                    await asyncio.sleep(QUEUE_POLL_PERIOD)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    bound_logger.info("SSE event stream cancelled.")
                    stop_event.set()
                    break

    return EventSourceResponse(event_stream())


@router.get(
    "/{wallet_id}/{topic}/{desired_state}",
    response_class=EventSourceResponse,
    summary="Wait for a desired state to be reached for some event for this wallet and topic "
    "`desired_state` may be `offer-received`, `transaction-acked`, `done`, etc.",
)
@inject
async def sse_subscribe_event_with_state(
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    desired_state: str,
    lookback_time: int = lookback_time_field,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    bound_logger = logger.bind(
        body={"wallet_id": wallet_id, "topic": topic, "desired_state": desired_state}
    )
    bound_logger.info(
        "SSE: GET request received: Subscribe to wallet event by topic, "
        "waiting for specific state"
    )

    # Special case: Endorsements only contain two fields: `state` and `transaction_id`.
    # Endorsement Listeners will query by state only, in order to get the relevant transaction id.
    # So, a problem arises because the Admin wallet can listen for "request-received",
    # and we may return transaction_ids matching that state, but they have already been endorsed.
    # So, instead of imposing an arbitrary sleep duration for the listeners, for the event to arrive,
    # we will instead only return endorsement records if their state in cache isn't also acked or endorsed
    # Therefore, before sending events, we will check the state, and use an ignore list, as follows.

    async def event_stream():
        ignore_list = []

        stop_event = asyncio.Event()
        event_generator_wrapper: EventGeneratorWrapper = (
            await sse_manager.sse_event_stream(
                wallet=wallet_id,
                topic=topic,
                lookback_time=lookback_time,
                stop_event=stop_event,
                duration=SSE_TIMEOUT,
            )
        )
        async with event_generator_wrapper as event_generator:
            background_tasks.add_task(check_disconnection, request, stop_event)

            async for event in event_generator:
                if await request.is_disconnected():
                    bound_logger.info("SSE event_stream: client disconnected.")
                    stop_event.set()
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
                        result = event.model_dump_json()
                        bound_logger.trace("Yielding SSE event: {}", result)
                        yield result  # Send the event
                        stop_event.set()
                        break  # End the generator
                except asyncio.QueueEmpty:
                    await asyncio.sleep(QUEUE_POLL_PERIOD)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    bound_logger.info("SSE event stream cancelled.")
                    stop_event.set()
                    break

    return EventSourceResponse(event_stream())


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}",
    response_class=EventSourceResponse,
    summary="Wait for a desired state to be reached for some event for this wallet and topic "
    "The `relevant_id` refers to a `transaction_id` when using topic `endorsements,"
    "or a `connection_id` on topics: `connections`, `credentials`, or `proofs`, etc."
    "`desired_state` may be `offer-received`, `transaction-acked`, `done`, etc.",
)
@inject
async def sse_subscribe_stream_with_fields(
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    lookback_time: int = lookback_time_field,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    bound_logger = logger.bind(
        body={"wallet_id": wallet_id, "topic": topic, field: field_id}
    )
    bound_logger.info(
        "SSE: GET request received: Subscribe to wallet events by topic, "
        "only events with specific field-id pairs"
    )

    async def event_stream():
        stop_event = asyncio.Event()
        event_generator_wrapper: EventGeneratorWrapper = (
            await sse_manager.sse_event_stream(
                wallet=wallet_id,
                topic=topic,
                lookback_time=lookback_time,
                stop_event=stop_event,
                duration=SSE_TIMEOUT,
            )
        )
        async with event_generator_wrapper as event_generator:
            background_tasks.add_task(check_disconnection, request, stop_event)

            async for event in event_generator:
                if await request.is_disconnected():
                    bound_logger.info("SSE event_stream: client disconnected.")
                    stop_event.set()
                    break
                try:
                    payload = dict(event.payload)  # to check if keys exist in payload
                    if field in payload and payload[field] == field_id:
                        result = event.model_dump_json()
                        bound_logger.trace("Yielding SSE event: {}", result)
                        yield result  # Send the event
                except asyncio.QueueEmpty:
                    await asyncio.sleep(QUEUE_POLL_PERIOD)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    bound_logger.info("SSE event stream cancelled.")
                    stop_event.set()
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
async def sse_subscribe_event_with_field_and_state(
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    lookback_time: int = lookback_time_field,
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    bound_logger = logger.bind(
        body={
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
            "desired_state": desired_state,
        }
    )
    bound_logger.info(
        "SSE: GET request received: Subscribe to wallet event by topic, "
        "waiting for payload with field-id pair and specific state"
    )

    async def event_stream():
        stop_event = asyncio.Event()
        event_generator_wrapper: EventGeneratorWrapper = (
            await sse_manager.sse_event_stream(
                wallet=wallet_id,
                topic=topic,
                lookback_time=lookback_time,
                stop_event=stop_event,
                duration=SSE_TIMEOUT,
            )
        )
        async with event_generator_wrapper as event_generator:
            background_tasks.add_task(check_disconnection, request, stop_event)

            async for event in event_generator:
                if await request.is_disconnected():
                    bound_logger.info("SSE event_stream: client disconnected.")
                    stop_event.set()
                    break
                try:
                    payload = dict(event.payload)  # to check if keys exist in payload
                    if (
                        field in payload
                        and payload[field] == field_id
                        and payload["state"] == desired_state
                    ):
                        result = event.model_dump_json()
                        bound_logger.trace("Yielding SSE event: {}", result)
                        yield result  # Send the event
                        stop_event.set()
                        break  # End the generator
                except asyncio.QueueEmpty:
                    await asyncio.sleep(QUEUE_POLL_PERIOD)
                except asyncio.CancelledError:
                    # This exception is thrown when the client disconnects.
                    bound_logger.info("SSE event stream cancelled.")
                    stop_event.set()
                    break

    return EventSourceResponse(event_stream())

import asyncio
from collections.abc import AsyncGenerator

from dependency_injector.wiring import Provide, inject
from fastapi import BackgroundTasks, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from shared import APIRouter
from shared.constants import DISCONNECT_CHECK_PERIOD, SSE_LOOK_BACK
from shared.log_config import get_logger
from waypoint.services.dependency_injection.container import Container
from waypoint.services.nats_service import NatsEventsProcessor

logger = get_logger(__name__)

router = APIRouter(
    prefix="/sse",
    tags=["waypoint"],
)


async def check_disconnect(request: Request, stop_event: asyncio.Event) -> None:
    """Check if the client has disconnected"""
    while not stop_event.is_set():
        if await request.is_disconnected():
            logger.debug("Waypoint client disconnected")
            stop_event.set()
        await asyncio.sleep(DISCONNECT_CHECK_PERIOD)


async def nats_event_stream_generator(
    *,
    nats_processor: NatsEventsProcessor,
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    group_id: str | None = None,
    look_back: int | None = None,
) -> AsyncGenerator[str, None]:
    """Generator for NATS events."""
    logger.debug("Starting NATS event stream generator")
    stop_event = asyncio.Event()

    async with nats_processor.process_events(
        group_id=group_id,
        wallet_id=wallet_id,
        topic=topic,
        state=desired_state,
        stop_event=stop_event,
        look_back=look_back,
    ) as event_generator:
        background_tasks.add_task(check_disconnect, request, stop_event)

        async for event, msg in event_generator:
            if await request.is_disconnected():
                logger.debug("Client disconnected")
                stop_event.set()
                break

            payload = event.payload
            if payload.get(field) == field_id:
                logger.trace("Event found yielding event {}", event)
                yield event.model_dump_json()
                await msg.ack()
                stop_event.set()
                break


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
    response_class=EventSourceResponse,
    summary="""
    Wait for a desired state to be reached for some event for this wallet and topic.
    """,
    description="""
    The `relevant_id` refers to a `transaction_id` when using topic `endorsements`,
    or a `connection_id` on topics: `connections`, `credentials`, or `proofs`, etc.
    `desired_state` may be `offer-received`, `transaction-acked`, `done`, etc.
    """,
)
@inject
async def sse_wait_for_event_with_field_and_state(
    request: Request,
    background_tasks: BackgroundTasks,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    group_id: str | None = Query(
        default=None, description="Group ID to which the wallet belongs"
    ),
    look_back: int | None = Query(
        default=SSE_LOOK_BACK,
        description="Number of seconds to look back for events before subscribing",
    ),
    nats_processor: NatsEventsProcessor = Depends(
        Provide[Container.nats_events_processor]
    ),
) -> EventSourceResponse:
    bound_logger = logger.bind(
        body={
            "wallet_id": wallet_id,
            "group_id": group_id,
            "topic": topic,
            field: field_id,
            "desired_state": desired_state,
        }
    )
    bound_logger.debug(
        "Waypoint: GET request received: Subscribe to wallet event by topic, "
        "waiting for payload with field-id pair and specific state"
    )

    event_stream = nats_event_stream_generator(
        nats_processor=nats_processor,
        request=request,
        background_tasks=background_tasks,
        wallet_id=wallet_id,
        topic=topic,
        field=field,
        field_id=field_id,
        desired_state=desired_state,
        group_id=group_id,
        look_back=look_back,
    )

    return EventSourceResponse(event_stream)

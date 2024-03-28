from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.dependencies.auth import (
    AcaPyAuthVerified,
    acapy_auth_verified,
    verify_wallet_access,
)
from app.services.sse import (
    sse_subscribe_event_with_field_and_state,
    sse_subscribe_event_with_state,
    sse_subscribe_stream_with_fields,
    sse_subscribe_wallet,
    sse_subscribe_wallet_topic,
)
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/sse", tags=["sse"])


group_id_field = Query(
    default=None,
    description="Group ID to which the wallet belongs",
)


@router.get(
    "/{wallet_id}", response_class=StreamingResponse, name="Subscribe to Wallet Events"
)
async def get_sse_subscribe_wallet(
    request: Request,
    wallet_id: str,
    group_id: Optional[str] = group_id_field,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    """
    Subscribe to server-side events for a specific wallet ID.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
    """
    logger.bind(body={"group_id": group_id, "wallet_id": wallet_id}).info(
        "GET request received: Subscribe to wallet events"
    )

    verify_wallet_access(auth, wallet_id)

    return StreamingResponse(
        sse_subscribe_wallet(
            request=request,
            group_id=group_id,
            wallet_id=wallet_id,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/{wallet_id}/{topic}",
    response_class=StreamingResponse,
    name="Subscribe to Wallet Events by Topic",
)
async def get_sse_subscribe_wallet_topic(
    request: Request,
    wallet_id: str,
    topic: str,
    group_id: Optional[str] = group_id_field,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    """
    Subscribe to server-side events for a specific wallet ID and topic.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
    """
    logger.bind(
        body={"group_id": group_id, "wallet_id": wallet_id, "topic": topic}
    ).info("GET request received: Subscribe to wallet events by topic")

    verify_wallet_access(auth, wallet_id)

    return StreamingResponse(
        sse_subscribe_wallet_topic(
            request=request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/{wallet_id}/{topic}/{desired_state}",
    response_class=StreamingResponse,
    name="Subscribe to a Wallet Event by Topic and Desired State",
)
async def get_sse_subscribe_event_with_state(
    request: Request,
    wallet_id: str,
    topic: str,
    desired_state: str,
    group_id: Optional[str] = group_id_field,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    """
    Subscribe to server-side events for a specific wallet ID and topic,
    and wait for an event that matches the desired state.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        desired_state: The desired state to be reached.
    """
    logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            "desired_state": desired_state,
        }
    ).info(
        "GET request received: Subscribe to wallet events by topic and desired state"
    )

    verify_wallet_access(auth, wallet_id)

    return StreamingResponse(
        sse_subscribe_event_with_state(
            request=request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            desired_state=desired_state,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}",
    response_class=StreamingResponse,
    name="Subscribe to Wallet Events by Topic and Field",
)
async def get_sse_subscribe_stream_with_fields(
    request: Request,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    group_id: Optional[str] = group_id_field,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    """
    Subscribe to server-side events for a specific wallet ID and topic, and
    filter the events for payloads containing a specific field and field ID pair.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        field: The field to which the wallet is subscribing.
        field_id: The ID of the field subscribing to the events.
    """
    logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
        }
    ).info("GET request received: Subscribe to wallet events by topic and select field")

    verify_wallet_access(auth, wallet_id)

    return StreamingResponse(
        sse_subscribe_stream_with_fields(
            request=request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
        ),
        media_type="text/event-stream",
    )


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
    response_class=StreamingResponse,
    name="Subscribe to a Wallet Event by Topic, Field, and Desired State",
)
async def get_sse_subscribe_event_with_field_and_state(
    request: Request,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    group_id: Optional[str] = group_id_field,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    """
    Wait for a desired state to be reached for some event for this wallet and topic,
    filtering for payloads that contain `field:field_id`.

    Args:
        wallet_id: The ID of the wallet subscribing to the events.
        topic: The topic to which the wallet is subscribing.
        field: The field to which the wallet is subscribing.
        field_id: The ID of the field subscribing to the events.
        desired_state: The desired state to be reached.
    """
    logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
            "desired_state": desired_state,
        }
    ).info("GET request received: Subscribe to wallet events by topic, field and state")

    verify_wallet_access(auth, wallet_id)

    return StreamingResponse(
        sse_subscribe_event_with_field_and_state(
            request=request,
            group_id=group_id,
            wallet_id=wallet_id,
            topic=topic,
            field=field,
            field_id=field_id,
            desired_state=desired_state,
        ),
        media_type="text/event-stream",
    )

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.dependencies.auth import (
    AcaPyAuthVerified,
    acapy_auth_verified,
    verify_wallet_access,
)
from app.services.event_handling.sse import sse_subscribe_event_with_field_and_state
from shared.constants import SSE_LOOK_BACK
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/sse", tags=["sse"])


group_id_query: str | None = Query(
    default=None,
    description="Group ID to which the wallet belongs",
    include_in_schema=False,
)


@router.get(
    "/{wallet_id}/{topic}/{field}/{field_id}/{desired_state}",
    response_class=StreamingResponse,
    name="Subscribe to a Wallet Event by Topic, Field, and Desired State",
)
async def get_sse_subscribe_event_with_field_and_state(  # noqa: D417
    request: Request,
    wallet_id: str,
    topic: str,
    field: str,
    field_id: str,
    desired_state: str,
    group_id: str | None = group_id_query,
    look_back: int | None = Query(
        default=SSE_LOOK_BACK, description="Number of seconds to look back for events"
    ),
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
) -> StreamingResponse:
    """Subscribe to SSE events wait for a desired state with a field filter.
    ---
    ***This endpoint can't be called on the swagger UI, as it requires a stream response.***

    Wait for a desired state to be reached for some event for this wallet and topic,
    filtering for payloads that contain `field:field_id`.

    example: `/{wallet_id}/credentials/connection_id/some-uuid/done` will stream a credential exchange event on a
    specific connection with state done.
    The field and field ID pair must be present in the payload (other than state) for the event to be streamed.
    The stream will be closed after the event is returned.

    Parameters
    ----------
        wallet_id:
            The ID of the wallet subscribing to the events.
        topic:
            The topic to which the wallet is subscribing.
        field:
            The field to which the wallet is subscribing.
        field_id:
            The ID of the field subscribing to the events.
        desired_state:
            The desired state to be reached.
        look_back:
            Number of seconds to look back for events before subscribing.

    """
    logger.bind(
        body={
            "group_id": group_id,
            "wallet_id": wallet_id,
            "topic": topic,
            field: field_id,
            "desired_state": desired_state,
        }
    ).debug(
        "GET request received: Subscribe to wallet events by topic, field and state"
    )

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
            look_back=look_back,
        ),
        media_type="text/event-stream",
    )

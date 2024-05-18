import asyncio

from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.dependencies.auth import (
    AcaPyAuthVerified,
    get_acapy_auth,
    get_acapy_auth_verified,
)
from app.services.event_handling.websocket_manager import WebsocketManager
from shared.log_config import get_logger

logger = get_logger(__name__)

DISCONNECT_CHECK_PERIOD = 0.1


async def get_websocket_api_key(websocket: WebSocket) -> str:
    for header, value in websocket.headers.items():
        if header.lower() == "x-api-key":
            return value
    return ""


async def websocket_auth(
    websocket: WebSocket,
    api_key: str = Depends(get_websocket_api_key),
) -> AcaPyAuthVerified:
    try:
        auth = get_acapy_auth(api_key)
        return get_acapy_auth_verified(auth)
    except HTTPException:
        await websocket.accept()  # Accept to send unauthorized message
        await websocket.send_text("Unauthorized")
        await websocket.close(code=1008)
        logger.info("Unauthorized WebSocket connection closed.")


async def handle_websocket(
    websocket: WebSocket,
    *,
    group_id: str,
    wallet_id: str,
    topic: str,
    auth: AcaPyAuthVerified,
) -> None:
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "topic": topic})
    bound_logger.debug("Accepting websocket")
    await websocket.accept()
    bound_logger.debug("Accepted websocket")

    if (
        not auth
        or (
            wallet_id and auth.wallet_id not in ("admin", wallet_id)
        )  # tenants can subscribe to their own wallets; admin can subscribe to any wallet
        or (
            not wallet_id and auth.wallet_id != "admin"
        )  # only admin can subscribe to topic (wallet_id == "")
    ):
        bound_logger.debug("Notifying user is unauthorized")
        await websocket.send_text("Unauthorized")
        await websocket.close(code=1008)
        bound_logger.info("Unauthorized WebSocket connection closed")
        return

    if not group_id and not wallet_id and not topic:
        bound_logger.debug("Notifying one of group, wallet, or topic must be specified")
        await websocket.send_text("One of group, wallet, or topic must be specified")
        await websocket.close(code=1008)
        bound_logger.info("Closed WebSocket connection with bad request")
        return

    uuid = None
    try:
        # Subscribe the WebSocket connection to the wallet / topic
        uuid = await WebsocketManager.subscribe(
            websocket, group_id=group_id, wallet_id=wallet_id, topic=topic
        )

        # Keep the connection open until the client disconnects
        while True:
            await asyncio.sleep(DISCONNECT_CHECK_PERIOD)
    except WebSocketDisconnect:
        bound_logger.info("WebSocket connection closed.")
        if uuid:
            await WebsocketManager.unsubscribe(uuid)
    except Exception:  # pylint: disable=W0718
        bound_logger.exception("Exception caught while handling websocket.")
        if uuid:
            await WebsocketManager.unsubscribe(uuid)

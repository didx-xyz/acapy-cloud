import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.event_handling.websocket_manager import WebsocketManager
from app.main import get_manager
from shared.dependencies.auth import AcaPyAuthVerified, acapy_auth_verified

LOGGER = logging.getLogger(__name__)
router = APIRouter()

# Singleton pattern
manager: WebsocketManager = get_manager()


async def handle_websocket(
    websocket: WebSocket,
    wallet_id: str,
    topic: str,
    auth: AcaPyAuthVerified,
):
    if auth.wallet_id not in ("admin", wallet_id):
        raise HTTPException(403, "Unauthorized")

    try:
        # Subscribe the WebSocket connection to the wallet / topic
        await manager.subscribe(websocket, wallet_id, topic)

        while True:
            data = await websocket.receive_text()
            # Forward the message to the original server
            await websocket.send_text(f"{wallet}: {data}")
    except WebSocketDisconnect:
        LOGGER.info("WebSocket connection closed")
    except Exception as e:
        LOGGER.error("Exception caught while handling websocket: %r", e)

    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
    await handle_websocket(websocket, wallet_id, "", auth)


@router.websocket("/ws/{wallet_id}/{topic}")
async def websocket_endpoint_topic(
    websocket: WebSocket,
    wallet_id: str,
    topic: str,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    await handle_websocket(websocket, wallet_id, topic, auth)


@router.websocket("/ws/topic/{topic}")
async def websocket_endpoint_admin(
    websocket: WebSocket,
    topic: str,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
):
    await handle_websocket(websocket, "", topic, auth)

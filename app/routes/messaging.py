from aries_cloudcontroller import PingRequest, PingRequestResponse, SendMessage
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions.handle_acapy_call import handle_acapy_call
from app.models.messaging import Message, TrustPingMsg
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/messaging", tags=["messaging"])


@router.post("/send-message", summary="Send a Message")
async def send_messages(
    message: Message,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """Send basic message
    ---

    Send a message to a tenant via a connection. The other tenant will receive
    the message on topic `basic-message` for their webhook events.

    See the Aries
    [Basic Message Protocol](https://github.com/hyperledger/aries-rfcs/blob/main/features/0095-basic-message/README.md)
    for more information.

    Request body:
    ---
        message: Message
            connection_id: str
                Connection ID of the connection to send the message to.
            content: str
                The message to send.

    Returns
    -------
        Status code 204

    """
    logger.debug("POST request received: Send message")
    request_body = SendMessage(content=message.content)
    async with client_from_auth(auth) as aries_controller:
        await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.basicmessage.send_message,
            conn_id=message.connection_id,
            body=request_body,
        )
    logger.debug("Successfully sent message.")


@router.post("/trust-ping", summary="Send Trust Ping")
async def send_trust_ping(
    trustping_msg: TrustPingMsg,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PingRequestResponse:
    """Send trust ping
    ---
    Send a trust ping to a connection to ensure that the connection is active and ready.

    See the Aries
    [Trust Ping Protocol](https://github.com/hyperledger/aries-rfcs/blob/main/features/0048-trust-ping/README.md)
    for more information.

    Request body:
    ---
        TrustPingMsg :
            connection_id: str
                Connection ID of the connection to send the trust ping to.
            comment: str
                Comment to include in the trust ping.

    Returns
    -------
        PingRequestResponse
            thread_id: str
                Thread ID of the ping message

    """
    logger.debug("POST request received: Send trust ping")
    request_body = PingRequest(comment=trustping_msg.comment)
    async with client_from_auth(auth) as aries_controller:
        response = await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.trustping.send_ping,
            conn_id=trustping_msg.connection_id,
            body=request_body,
        )
    logger.debug("Successfully sent trust ping.")
    return response

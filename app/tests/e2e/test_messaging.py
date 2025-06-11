import time

import pytest

from app.models.messaging import Message, TrustPingMsg
from app.routes.messaging import router
from app.tests.util.connections import BobAliceConnect
from shared import RichAsyncClient

MESSAGING_BASE_PATH = router.prefix


@pytest.mark.anyio
async def test_send_trust_ping(
    bob_and_alice_connection: BobAliceConnect, alice_member_client: RichAsyncClient
):
    trustping_msg = TrustPingMsg(
        connection_id=bob_and_alice_connection.alice_connection_id, comment="Asdf"
    )

    response = await alice_member_client.post(
        MESSAGING_BASE_PATH + "/trust-ping", json=trustping_msg.model_dump()
    )
    response_data = response.json()

    assert response.status_code == 200
    assert "thread_id" in response_data
    time.sleep(1)  # Wait for ping to be sent before deleting wallet


@pytest.mark.anyio
async def test_send_message(
    bob_and_alice_connection: BobAliceConnect, alice_member_client: RichAsyncClient
):
    message = Message(
        connection_id=bob_and_alice_connection.alice_connection_id, content="Asdf"
    )

    response = await alice_member_client.post(
        MESSAGING_BASE_PATH + "/send-message", json=message.model_dump()
    )

    assert response.status_code == 200

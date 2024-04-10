import json
import logging

import pytest
from httpx import ReadTimeout, Response, Timeout

from app.tests.util.ecosystem_connections import BobAliceConnect
from app.tests.util.webhooks import get_wallet_id_from_async_client
from shared import WEBHOOKS_URL, RichAsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.anyio
async def test_sse_subscribe_wallet_topic(
    alice_member_client: RichAsyncClient,
    bob_and_alice_connection: BobAliceConnect,
):
    alice_wallet_id = get_wallet_id_from_async_client(alice_member_client)
    alice_connection_id = bob_and_alice_connection.alice_connection_id

    topic = "connections"
    url = f"{WEBHOOKS_URL}/sse/{alice_wallet_id}/{topic}"

    sse_response = await get_sse_stream_response(url)

    logger.debug("SSE stream response: %s", sse_response)
    json_lines = response_to_json(sse_response)
    logger.debug("Response as json: %s", json_lines)
    assert any(
        line["topic"] == topic
        and line["wallet_id"] == alice_wallet_id
        and line["payload"]["connection_id"] == alice_connection_id
        for line in json_lines
    )


@pytest.mark.anyio
async def test_sse_subscribe_event_state(
    alice_member_client: RichAsyncClient,
    bob_and_alice_connection: BobAliceConnect,
):
    alice_wallet_id = get_wallet_id_from_async_client(alice_member_client)
    alice_connection_id = bob_and_alice_connection.alice_connection_id

    topic = "connections"
    state = "completed"

    url = f"{WEBHOOKS_URL}/sse/{alice_wallet_id}/{topic}/{state}"
    sse_response = await listen_for_event(url)
    logger.debug("SSE stream response: %s", sse_response)

    assert (
        sse_response["topic"] == topic
        and sse_response["wallet_id"] == alice_wallet_id
        and sse_response["payload"]["state"] == state
        and sse_response["payload"]["connection_id"] == alice_connection_id
    )


@pytest.mark.anyio
async def test_sse_subscribe_filtered_stream(
    alice_member_client: RichAsyncClient,
    bob_and_alice_connection: BobAliceConnect,
):
    alice_wallet_id = get_wallet_id_from_async_client(alice_member_client)
    alice_connection_id = bob_and_alice_connection.alice_connection_id

    topic = "connections"
    field = "connection_id"

    url = f"{WEBHOOKS_URL}/sse/{alice_wallet_id}/{topic}/{field}/{alice_connection_id}"

    sse_response = await get_sse_stream_response(url)

    logger.debug("SSE stream response: %s", sse_response)
    json_lines = response_to_json(sse_response)
    logger.debug("Response as json: %s", json_lines)
    assert all(
        line["topic"] == topic
        and line["wallet_id"] == alice_wallet_id
        and line["payload"]["connection_id"] == alice_connection_id
        for line in json_lines
    )


@pytest.mark.anyio
async def test_sse_subscribe_event(
    alice_member_client: RichAsyncClient,
    bob_and_alice_connection: BobAliceConnect,
):
    alice_wallet_id = get_wallet_id_from_async_client(alice_member_client)
    alice_connection_id = bob_and_alice_connection.alice_connection_id

    topic = "connections"
    field = "connection_id"
    state = "completed"

    url = f"{WEBHOOKS_URL}/sse/{alice_wallet_id}/{topic}/{field}/{alice_connection_id}/{state}"
    sse_response = await listen_for_event(url)
    logger.debug("SSE stream response: %s", sse_response)

    assert (
        sse_response["topic"] == topic
        and sse_response["wallet_id"] == alice_wallet_id
        and sse_response["payload"][field] == alice_connection_id
        and sse_response["payload"]["state"] == state
    )


async def get_sse_stream_response(url, duration=2) -> Response:
    timeout = Timeout(duration)
    try:
        async with RichAsyncClient(timeout=timeout) as client:
            async with client.stream("GET", url) as response:
                response_text = ""
                async for line in response.aiter_lines():
                    response_text += line
    except (TimeoutError, ReadTimeout):
        # Closing connection gracefully, return the response text read so far
        pass
    finally:
        return response_text


def response_to_json(response_text):
    # Split the response into lines
    lines = response_text.split("data: ")

    # # Parse each line as JSON
    json_lines = [json.loads(line) for line in lines if line]

    return json_lines


async def listen_for_event(url, duration=10):
    timeout = Timeout(duration)
    async with RichAsyncClient(timeout=timeout) as client:
        async with client.stream("GET", url) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    return json.loads(data)

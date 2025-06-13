from typing import NoReturn

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ConnectTimeout, HTTPStatusError, Request, Response

from shared.util.rich_async_client import RichAsyncClient

test_url = "https://test.com"
retry_duration = 0.05


@pytest.mark.anyio
async def test_rich_async_client_initialization():
    client = RichAsyncClient(
        name="TestClient", retries=2, retry_on=[502], retry_wait_seconds=retry_duration
    )
    assert client.name == "TestClient - HTTP"
    assert client.retries == 2
    assert client.retry_on == [502]
    assert client.retry_wait_seconds == retry_duration


@pytest.mark.anyio
async def test_rich_async_client_get_success(
    mock_response,  # pylint: disable=redefined-outer-name,unused-argument
):
    async with RichAsyncClient() as client:
        response = await client.get(test_url)
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.mark.anyio
async def test_rich_async_client_post_success(
    mock_response,  # pylint: disable=redefined-outer-name,unused-argument
):
    async with RichAsyncClient() as client:
        response = await client.post(test_url, json={"key": "value"})
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.mark.anyio
async def test_rich_async_client_put_success(
    mock_response,  # pylint: disable=redefined-outer-name,unused-argument
):
    async with RichAsyncClient() as client:
        response = await client.put(test_url, json={"key": "value"})
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.mark.anyio
async def test_rich_async_client_delete_success(
    mock_response,  # pylint: disable=redefined-outer-name,unused-argument
):
    async with RichAsyncClient() as client:
        response = await client.delete(test_url)
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.mark.anyio
async def test_rich_async_client_retry_on_502(monkeypatch):
    # Use a list to simulate the sequence of responses
    responses = [
        Response(502, request=Request("GET", test_url), text="Bad Gateway"),
        Response(200, request=Request("GET", test_url), text="Success"),
    ]

    async def mock_get(_, __) -> Response:
        # Pop the first response from the list
        response = responses.pop(0)
        if response.status_code == 502:
            raise HTTPStatusError(
                "Bad Gateway", request=response.request, response=response
            )
        return response

    monkeypatch.setattr(AsyncClient, "get", mock_get)

    async with RichAsyncClient(
        retries=2, retry_on=[502], retry_wait_seconds=retry_duration
    ) as client:
        response = await client.get(test_url)
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.mark.anyio
async def test_rich_async_client_no_retry_on_404(monkeypatch):
    async def mock_get(_, __) -> NoReturn:
        # Simulate a 404 error
        response = Response(404, request=Request("GET", test_url), text="Not Found")
        raise HTTPStatusError("Not Found", request=response.request, response=response)

    monkeypatch.setattr(AsyncClient, "get", mock_get)

    async with RichAsyncClient(
        retries=2, retry_on=[502], retry_wait_seconds=retry_duration
    ) as client:
        with pytest.raises(HTTPException) as exc_info:
            await client.get(test_url)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not Found"


@pytest.mark.anyio
async def test_rich_async_client_retry_on_connect_timeout(monkeypatch):
    attempts = []

    async def mock_get(_, __) -> Response:
        if len(attempts) < 1:
            attempts.append(1)
            raise ConnectTimeout("Connection timed out")
        return Response(200, request=Request("GET", test_url), text="Success")

    monkeypatch.setattr(AsyncClient, "get", mock_get)

    async with RichAsyncClient(
        retries=2, retry_on=[502], retry_wait_seconds=retry_duration
    ) as client:
        response = await client.get(test_url)
        assert response.status_code == 200
        assert response.text == "Success"


@pytest.fixture
def mock_response(monkeypatch) -> None:
    async def mock_send(*_, **__) -> Response:
        return Response(200, request=Request("GET", test_url), text="Success")

    monkeypatch.setattr(RichAsyncClient, "_request_with_retries", mock_send)

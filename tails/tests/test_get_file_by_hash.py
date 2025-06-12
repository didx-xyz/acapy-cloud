from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from tails.routers.tails import get_file_by_hash


@pytest.mark.anyio
async def test_get_file_by_hash_success() -> None:
    tails_hash = "testhash"
    mock_s3_client = MagicMock()
    mock_head_response = {
        "ContentType": "application/octet-stream",
        "ContentLength": 123,
    }
    mock_body = MagicMock()
    # Simulate two chunks then EOF
    mock_body.read.side_effect = [b"abc", b"def", b""]

    mock_s3_response = {"Body": mock_body}

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        mock_s3_client.head_object.return_value = mock_head_response
        mock_s3_client.get_object.return_value = mock_s3_response

        response = await get_file_by_hash(tails_hash)
        assert isinstance(response, StreamingResponse)
        # Check headers
        assert (
            response.headers["Content-Disposition"]
            == f"attachment; filename={tails_hash}"
        )
        assert response.headers["Content-Length"] == str(
            mock_head_response["ContentLength"]
        )
        assert response.media_type == mock_head_response["ContentType"]

        # Test streaming generator yields correct chunks
        body = b"".join([chunk async for chunk in response.body_iterator])
        assert body == b"abcdef"


@pytest.mark.anyio
async def test_get_file_by_hash_not_found() -> None:
    tails_hash = "notfound"

    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    with patch("tails.routers.tails.get_s3_client") as mock_get_s3_client:
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client
        mock_s3_client.head_object.side_effect = ClientError(
            error_response, "head_object"
        )

        with pytest.raises(HTTPException) as exc:
            await get_file_by_hash(tails_hash)
        assert exc.value.status_code == 404
        assert exc.value.detail == "File not found"


@pytest.mark.anyio
async def test_get_file_by_hash_s3_error() -> None:
    tails_hash = "error"

    error_response = {"Error": {"Code": "OtherError"}}
    with patch("tails.routers.tails.get_s3_client") as mock_get_s3_client:
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client
        mock_s3_client.head_object.side_effect = ClientError(
            error_response, "head_object"
        )

        with pytest.raises(HTTPException) as exc:
            await get_file_by_hash(tails_hash)
        assert exc.value.status_code == 500
        assert "S3 download failed" in exc.value.detail

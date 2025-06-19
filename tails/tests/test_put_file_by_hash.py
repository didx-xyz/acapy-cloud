import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from tails.routers.tails import put_file_by_hash


def setup_temp_file_mock(mock_tmpfile, file_content, validation_read=b"\x00\x02"):
    """Helper to setup temp file mock as async context manager"""
    tmp_file = AsyncMock()
    tmp_file.write = AsyncMock()
    # Simulate sequence of reads: validation read, then any additional reads
    tmp_file.read = AsyncMock(side_effect=[validation_read, file_content, b""])
    tmp_file.tell = AsyncMock(return_value=len(file_content))
    tmp_file.seek = AsyncMock()

    # Setup async context manager
    mock_tmpfile.return_value.__aenter__.return_value = tmp_file

    async def _mock_aexit(*_) -> None:
        """Create proper async __aexit__ that doesn't suppress exceptions"""
        await asyncio.sleep(0)

    mock_tmpfile.return_value.__aexit__ = _mock_aexit
    return tmp_file


@pytest.mark.anyio
async def test_put_file_by_hash_success():
    tails_hash = "testhash"
    file_content = b"\x00\x02" + b"a" * 128  # valid start, valid size
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to raise 404 (file doesn't exist)
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with patch("aiofiles.tempfile.TemporaryFile") as mock_tmpfile:
            setup_temp_file_mock(mock_tmpfile, file_content)

            # Patch hash calculation to match tails_hash
            with (
                patch("tails.routers.tails.hashlib.sha256") as mock_sha256,
                patch(
                    "tails.routers.tails.base58.b58encode",
                    return_value=tails_hash.encode(),
                ),
            ):
                mock_sha = MagicMock()
                mock_sha.digest.return_value = b"digest"
                mock_sha256.return_value = mock_sha

                response = await put_file_by_hash(tails_hash, mock_upload_file)
                assert isinstance(response, JSONResponse)
                assert response.status_code == 200
                assert response.body
                assert tails_hash in response.body.decode()


@pytest.mark.anyio
async def test_put_file_by_hash_already_exists():
    """Test that we get 409 when file already exists"""
    tails_hash = "existinghash"
    file_content = b"\x00\x02" + b"a" * 128
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to succeed (file exists)
    mock_s3_client.head_object.return_value = {"ContentLength": 130}

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with pytest.raises(HTTPException) as exc:
            await put_file_by_hash(tails_hash, mock_upload_file)
        assert exc.value.status_code == 409
        assert f"File with hash {tails_hash} already exists" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_hash_mismatch():
    tails_hash = "expectedhash"
    file_content = b"\x00\x02" + b"a" * 128
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to raise 404 (file doesn't exist)
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with patch("aiofiles.tempfile.TemporaryFile") as mock_tmpfile:
            setup_temp_file_mock(mock_tmpfile, file_content)

            with (
                patch("tails.routers.tails.hashlib.sha256") as mock_sha256,
                patch(
                    "tails.routers.tails.base58.b58encode", return_value=b"wronghash"
                ),
            ):
                mock_sha = MagicMock()
                mock_sha.digest.return_value = b"digest"
                mock_sha256.return_value = mock_sha

                with pytest.raises(HTTPException) as exc:
                    await put_file_by_hash(tails_hash, mock_upload_file)
                assert exc.value.status_code == 400
                assert "Hash mismatch" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_invalid_start():
    tails_hash = "testhash"
    file_content = b"\x01\x02" + b"a" * 128  # invalid start
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to raise 404 (file doesn't exist)
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with patch("aiofiles.tempfile.TemporaryFile") as mock_tmpfile:
            setup_temp_file_mock(
                mock_tmpfile, file_content, validation_read=b"\x01\x02"
            )

            with (
                patch("tails.routers.tails.hashlib.sha256") as mock_sha256,
                patch(
                    "tails.routers.tails.base58.b58encode",
                    return_value=tails_hash.encode(),
                ),
            ):
                mock_sha = MagicMock()
                mock_sha.digest.return_value = b"digest"
                mock_sha256.return_value = mock_sha

                with pytest.raises(HTTPException) as exc:
                    await put_file_by_hash(tails_hash, mock_upload_file)
                assert exc.value.status_code == 400
                assert "File must start" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_invalid_size():
    tails_hash = "testhash"
    file_content = b"\x00\x02" + b"a" * 127  # not a multiple of 128 after 2 bytes
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to raise 404 (file doesn't exist)
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with patch("aiofiles.tempfile.TemporaryFile") as mock_tmpfile:
            setup_temp_file_mock(mock_tmpfile, file_content)

            with (
                patch("tails.routers.tails.hashlib.sha256") as mock_sha256,
                patch(
                    "tails.routers.tails.base58.b58encode",
                    return_value=tails_hash.encode(),
                ),
            ):
                mock_sha = MagicMock()
                mock_sha.digest.return_value = b"digest"
                mock_sha256.return_value = mock_sha

                with pytest.raises(HTTPException) as exc:
                    await put_file_by_hash(tails_hash, mock_upload_file)
                assert "Tails file is not the correct size" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_s3_error():
    tails_hash = "testhash"
    file_content = b"\x00\x02" + b"a" * 128
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    error_response = {"Error": {"Code": "OtherError"}}
    mock_s3_client = MagicMock()
    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        # Mock head_object to raise 404 (file doesn't exist)
        not_found_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_s3_client.head_object.side_effect = ClientError(
            not_found_response, "head_object"
        )
        # Mock upload_fileobj to raise error
        mock_s3_client.upload_fileobj.side_effect = ClientError(
            error_response, "upload_fileobj"
        )

        with patch("aiofiles.tempfile.TemporaryFile") as mock_tmpfile:
            setup_temp_file_mock(mock_tmpfile, file_content)

            with (
                patch("tails.routers.tails.hashlib.sha256") as mock_sha256,
                patch(
                    "tails.routers.tails.base58.b58encode",
                    return_value=tails_hash.encode(),
                ),
            ):
                mock_sha = MagicMock()
                mock_sha.digest.return_value = b"digest"
                mock_sha256.return_value = mock_sha

                with pytest.raises(HTTPException) as exc:
                    await put_file_by_hash(tails_hash, mock_upload_file)
                assert exc.value.status_code == 500
                assert "S3 upload failed" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_generic_error():
    tails_hash = "testhash"
    file_content = b"\x00\x02" + b"a" * 128
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    with patch("tails.routers.tails.get_s3_client", side_effect=Exception("fail")):
        with pytest.raises(HTTPException) as exc:
            await put_file_by_hash(tails_hash, mock_upload_file)
        assert exc.value.status_code == 500
        assert "Upload failed" in exc.value.detail


@pytest.mark.anyio
async def test_put_file_by_hash_head_object_other_error():
    """Test that non-404 errors from head_object are handled properly"""
    tails_hash = "testhash"
    file_content = b"\x00\x02" + b"a" * 128
    mock_upload_file = AsyncMock()
    mock_upload_file.read = AsyncMock(side_effect=[file_content, b""])
    mock_upload_file.content_type = "application/octet-stream"

    mock_s3_client = MagicMock()
    # Mock head_object to raise a non-404 error
    error_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
    mock_s3_client.head_object.side_effect = ClientError(error_response, "head_object")

    with patch("tails.routers.tails.get_s3_client", return_value=mock_s3_client):
        with pytest.raises(HTTPException) as exc:
            await put_file_by_hash(tails_hash, mock_upload_file)
        assert exc.value.status_code == 500
        assert "Error checking file existence" in exc.value.detail

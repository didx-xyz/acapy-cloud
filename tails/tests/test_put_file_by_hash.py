from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from tails.routers.tails import put_file_by_hash


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
        with patch("tempfile.TemporaryFile") as mock_tmpfile:
            # Setup temp file mock
            tmp_file = MagicMock()
            tmp_file.__enter__.return_value = tmp_file
            tmp_file.read.side_effect = [
                b"\x00\x02",
                file_content,
                b"",
            ]  # for .read(2) and .read()
            tmp_file.tell.return_value = len(file_content)
            tmp_file.seek = MagicMock()
            mock_tmpfile.return_value = tmp_file

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
        with patch("tempfile.TemporaryFile") as mock_tmpfile:
            tmp_file = MagicMock()
            tmp_file.__enter__.return_value = tmp_file
            tmp_file.read.side_effect = [b"\x00\x02", file_content, b""]
            tmp_file.tell.return_value = len(file_content)
            tmp_file.seek = MagicMock()
            mock_tmpfile.return_value = tmp_file

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
        with patch("tempfile.TemporaryFile") as mock_tmpfile:
            tmp_file = MagicMock()
            tmp_file.__enter__.return_value = tmp_file
            tmp_file.read.side_effect = [b"\x01\x02", file_content, b""]
            tmp_file.tell.return_value = len(file_content)
            tmp_file.seek = MagicMock()
            mock_tmpfile.return_value = tmp_file

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
        with patch("tempfile.TemporaryFile") as mock_tmpfile:
            tmp_file = MagicMock()
            tmp_file.__enter__.return_value = tmp_file
            tmp_file.read.side_effect = [b"\x00\x02", file_content, b""]
            tmp_file.tell.return_value = len(file_content)
            tmp_file.seek = MagicMock()
            mock_tmpfile.return_value = tmp_file

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
    with patch("tails.routers.tails.get_s3_client") as mock_get_s3_client:
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client
        # Mock head_object to raise 404 (file doesn't exist)
        not_found_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_s3_client.head_object.side_effect = ClientError(
            not_found_response, "head_object"
        )

        with patch("tempfile.TemporaryFile") as mock_tmpfile:
            tmp_file = MagicMock()
            tmp_file.__enter__.return_value = tmp_file
            tmp_file.read.side_effect = [b"\x00\x02", file_content, b""]
            tmp_file.tell.return_value = len(file_content)
            tmp_file.seek = MagicMock()
            mock_tmpfile.return_value = tmp_file

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

                mock_s3_client.upload_fileobj.side_effect = ClientError(
                    error_response, "upload_fileobj"
                )
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

import hashlib
import os
from collections.abc import Generator

import aiofiles
import base58
from boto3 import client as boto_client
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from shared import APIRouter
from shared.constants import BUCKET_NAME
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    tags=["tails"],
)


# Initialize S3 client
def get_s3_client() -> BaseClient:
    return boto_client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL", None),
    )


@router.get("/hash/{tails_hash}")
async def get_file_by_hash(
    tails_hash: str,
) -> StreamingResponse:
    """Stream file content from S3"""
    try:
        s3_client = get_s3_client()

        # Get object metadata first
        head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=tails_hash)
        content_type = head_response.get("ContentType", "application/octet-stream")
        file_size = head_response["ContentLength"]

        # Get the object
        s3_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=tails_hash)

        # Create streaming response
        def generate() -> Generator[bytes, None, None]:
            try:
                # Read in chunks to avoid loading entire file into memory
                while True:
                    chunk = s3_response["Body"].read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk
            finally:
                s3_response["Body"].close()

        # Extract filename from s3_key
        filename = tails_hash.split("/")[-1]

        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(file_size),
            },
        )

    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            raise HTTPException(status_code=404, detail="File not found") from e
        raise HTTPException(status_code=500, detail=f"S3 download failed: {e!s}") from e


@router.put("/hash/{tails_hash}")
async def put_file_by_hash(
    tails_hash: str,
    tails: UploadFile = File(...),
) -> JSONResponse:
    """Upload a single file to S3."""
    sha256 = hashlib.sha256()

    try:
        logger.debug("File name: {}", tails.filename)

        s3_client = get_s3_client()

        # Check if the file already exists
        try:
            logger.debug("Checking if file with hash {} exists in S3", tails_hash)
            s3_client.head_object(Bucket=BUCKET_NAME, Key=tails_hash)
            raise HTTPException(
                status_code=409, detail=f"File with hash {tails_hash} already exists."
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                logger.error(f"Error checking file existence: {e!s}")
                raise HTTPException(
                    status_code=500, detail=f"Error checking file existence: {e!s}"
                ) from e

        # Use temporary file to calculate hash and validate content
        async with aiofiles.tempfile.TemporaryFile() as tmp_file:
            logger.debug("Using temporary file for hash calculation and validation")
            # Read file in chunks to avoid memory issues
            chunk_size = 8192  # 8KB chunks

            while True:
                chunk = await tails.read(chunk_size)
                if not chunk:
                    break

                sha256.update(chunk)
                await tmp_file.write(chunk)

            logger.debug("Finished reading upload file")
            logger.debug("SHA256 hash of uploaded file: {}", sha256.hexdigest())
            # Calculate final hash
            digest = sha256.digest()
            b58_digest = base58.b58encode(digest).decode("utf-8")

            # Validate hash matches expected
            if tails_hash != b58_digest:
                logger.error(f"Hash mismatch: Expected {tails_hash}, got {b58_digest}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Hash mismatch. Expected: {tails_hash}, Got: {b58_digest}",
                )

            logger.debug("Checking file content starts with '00 02'")
            tmp_file.seek(0)
            if tmp_file.read(2) != b"\x00\x02":
                logger.error("File does not start with '00 02'")
                raise HTTPException(
                    status_code=400, detail='File must start with "00 02".'
                )

            # Since each tail is 128 bytes, tails file size must be a multiple of 128
            # plus the 2-byte version tag
            logger.debug("Checking file size is a multiple of 128 bytes")
            tmp_file.seek(0, 2)
            if (tmp_file.tell() - 2) % 128 != 0:
                logger.error("Tails file is not the correct size.")
                raise HTTPException(
                    status_code=400, detail="Tails file is not the correct size."
                )

            logger.debug("File content validated successfully, uploading to S3")
            tmp_file.seek(0)  # Reset file pointer to the beginning
            # Upload file to S3
            s3_client.upload_fileobj(
                tmp_file,
                BUCKET_NAME,
                tails_hash,
                ExtraArgs={
                    "ContentType": tails.content_type or "application/octet-stream"
                },
            )

        return JSONResponse(
            status_code=200,
            content={
                "text": tails_hash,
            },
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e!s}") from e
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e!s}") from e

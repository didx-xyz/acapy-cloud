from typing import AsyncGenerator

import pytest

from app.tests.util.trust_registry import register_issuer_key
from shared import RichAsyncClient


@pytest.fixture(scope="function")
async def register_issuer_key_ed25519(
    faber_anoncreds_client: RichAsyncClient,
) -> AsyncGenerator[str, None]:
    async with register_issuer_key(faber_anoncreds_client, "ed25519") as did:
        yield did

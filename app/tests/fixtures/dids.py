from typing import AsyncGenerator

import pytest

from app.tests.util.trust_registry import register_issuer_key
from shared import RichAsyncClient


@pytest.fixture(scope="function")
async def register_issuer_key_ed25519(
    faber_indy_client: RichAsyncClient,
) -> AsyncGenerator[str, None]:
    async with register_issuer_key(faber_indy_client, "ed25519") as did:
        yield did


@pytest.fixture(scope="function")
async def register_issuer_key_bbs(
    faber_indy_client: RichAsyncClient,
) -> AsyncGenerator[str, None]:
    async with register_issuer_key(faber_indy_client, "bls12381g2") as did:
        yield did

from unittest.mock import AsyncMock, MagicMock

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    EndorseTransactionApi,
    SchemaApi,
    ServerApi,
)


@pytest.fixture(scope="session")
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})


@pytest.fixture
def mock_acapy_client():
    client = MagicMock(spec=AcaPyClient)
    client.endorse_transaction = MagicMock(spec=EndorseTransactionApi)
    client.schema = MagicMock(spec=SchemaApi)
    client.server = MagicMock(spec=ServerApi)
    client.endorse_transaction.get_transaction = AsyncMock()
    client.endorse_transaction.endorse_transaction = AsyncMock()
    client.schema.get_schema = AsyncMock()
    client.server.get_config = AsyncMock()
    return client

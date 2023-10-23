import pytest

from app.routes.connections import router
from shared import CLOUDAPI_URL
from shared.util.rich_async_client import RichAsyncClient

CONNECTIONS_BASE_PATH = router.prefix


@pytest.mark.anyio
async def test_error_handler():
    async with RichAsyncClient(
        base_url=CLOUDAPI_URL, raise_status_error=False
    ) as client:
        response = await client.get(CONNECTIONS_BASE_PATH)
        assert response.status_code == 403
        assert response.text == '{"detail":"Not authenticated"}'

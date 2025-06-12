from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from shared.util.resolve_cheqd_resources import resolve_cheqd_schema


@pytest.mark.anyio
async def test_resolve_cheqd_schema_success() -> None:
    mock_response = Mock()
    mock_response.json.return_value = {"id": "schema1", "name": "Test Schema"}
    with (
        patch(
            "shared.util.resolve_cheqd_resources.client.get",
            AsyncMock(return_value=mock_response),
        ),
        patch("shared.util.resolve_cheqd_resources.logger") as mock_logger,
    ):
        result = await resolve_cheqd_schema("schema1")
        assert result == {"id": "schema1", "name": "Test Schema"}
        mock_logger.debug.assert_called_with(
            "Resolving Cheqd schema with schema_id: schema1"
        )


@pytest.mark.anyio
async def test_resolve_cheqd_schema_http_exception() -> None:
    http_exc = HTTPException(status_code=404, detail="Not found")
    with (
        patch(
            "shared.util.resolve_cheqd_resources.client.get",
            AsyncMock(side_effect=http_exc),
        ),
        patch("shared.util.resolve_cheqd_resources.logger") as mock_logger,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_cheqd_schema("schema404")
        assert exc_info.value.status_code == 404
        mock_logger.error.assert_called_with(
            "HTTPException while resolving schema with schema_id schema404: Not found"
        )


@pytest.mark.anyio
async def test_resolve_cheqd_schema_unexpected_exception() -> None:
    with (
        patch(
            "shared.util.resolve_cheqd_resources.client.get",
            AsyncMock(side_effect=Exception("boom")),
        ),
        patch("shared.util.resolve_cheqd_resources.logger") as mock_logger,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await resolve_cheqd_schema("schema500")
        assert exc_info.value.status_code == 500
        mock_logger.error.assert_called()

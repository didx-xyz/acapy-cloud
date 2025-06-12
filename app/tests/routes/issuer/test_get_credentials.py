from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.exceptions.cloudapi_exception import CloudApiException
from app.routes.issuer import get_credentials


@pytest.mark.anyio
@pytest.mark.parametrize("mock_v2_records", [[], ["v2_rec"]])
async def test_get_credentials_success(mock_v2_records) -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.issuer.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.issuer.IssuerV2.get_records",
            return_value=mock_v2_records,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await get_credentials(state=None, auth="mocked_auth")

        assert response == mock_v2_records


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (CloudApiException, 400, "Bad request"),
        (CloudApiException, 404, "Not found"),
        (CloudApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_credentials_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
) -> None:
    mock_aries_controller = AsyncMock()
    issuer = AsyncMock()
    issuer.get_records = AsyncMock(
        side_effect=exception_class(
            status_code=expected_status_code, detail=expected_detail
        )
    )

    with (
        patch("app.routes.issuer.client_from_auth") as mock_client_from_auth,
        patch("app.routes.issuer.IssuerV2.get_records", new=issuer.get_records),
        pytest.raises(HTTPException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credentials(state=None, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code

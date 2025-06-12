from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.exceptions.cloudapi_exception import CloudApiException
from app.routes.issuer import get_credential
from app.services.issuer.acapy_issuer_v2 import IssuerV2


@pytest.mark.anyio
async def test_get_credential_success():
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.get_record = AsyncMock()

    with (
        patch("app.routes.issuer.client_from_auth") as mock_client_from_auth,
        patch("app.routes.issuer.IssuerV2.get_record", new=issuer.get_record),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credential(credential_exchange_id="test_id", auth="mocked_auth")

        IssuerV2.get_record.assert_awaited_once_with(
            controller=mock_aries_controller, credential_exchange_id="test_id"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (CloudApiException, 400, "Bad request"),
        (CloudApiException, 404, "Not found"),
        (CloudApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_credential_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.get_record = AsyncMock(
        side_effect=exception_class(
            status_code=expected_status_code, detail=expected_detail
        )
    )

    with (
        patch("app.routes.issuer.client_from_auth") as mock_client_from_auth,
        patch("app.routes.issuer.IssuerV2.get_record", new=issuer.get_record),
        pytest.raises(CloudApiException, match=expected_detail) as exc,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credential(credential_exchange_id="test_id", auth="mocked_auth")

    assert exc.value.status_code == expected_status_code

from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import DID, DIDList
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)

from app.routes.wallet.dids import list_dids

sample_did = DID(
    did="did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6",
    key_type="ed25519",
    method="cheqd",
    posture="posted",
    verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
)


@pytest.mark.anyio
@pytest.mark.parametrize("return_list", [DIDList(), DIDList(results=[sample_did])])
async def test_list_dids_success(return_list):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.wallet.get_dids = AsyncMock(return_value=return_list)

    with patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth:
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await list_dids(auth="mocked_auth")

        if not return_list.results:
            assert response == []
        else:
            assert response == return_list.results

        mock_aries_controller.wallet.get_dids.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_list_dids_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_get_dids = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(exception_class, match=expected_detail) as exc,
        patch("app.routes.wallet.dids.handle_acapy_call", mock_get_dids),
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await list_dids(auth="mocked_auth")

    assert exc.value.status == expected_status_code

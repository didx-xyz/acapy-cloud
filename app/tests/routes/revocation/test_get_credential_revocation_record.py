from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.revocation import get_credential_revocation_record


@pytest.mark.anyio
@pytest.mark.parametrize(
    "credential_exchange_id, credential_revocation_id, revocation_registry_id",
    [("a", None, None), (None, "b", "c")],
)
async def test_get_credential_revocation_record_success(
    credential_exchange_id, credential_revocation_id, revocation_registry_id
):
    mock_aries_controller = AsyncMock()
    mock_get_revocation_record = AsyncMock()

    with patch(
        "app.routes.revocation.client_from_auth"
    ) as mock_client_from_auth, patch(
        "app.services.revocation_registry.get_credential_revocation_record",
        mock_get_revocation_record,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credential_revocation_record(
            credential_exchange_id,
            credential_revocation_id,
            revocation_registry_id,
            auth="mocked_auth",
        )

        mock_get_revocation_record.assert_awaited_once_with(
            controller=mock_aries_controller,
            credential_exchange_id=credential_exchange_id,
            credential_revocation_id=credential_revocation_id,
            revocation_registry_id=revocation_registry_id,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_get_credential_revocation_record_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.anoncreds_revocation.get_cred_rev_record = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.revocation.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException, match=expected_detail
    ) as exc:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await get_credential_revocation_record(
            credential_exchange_id=MagicMock(), auth="mocked_auth"
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
@pytest.mark.parametrize(
    "credential_exchange_id, credential_revocation_id, revocation_registry_id",
    [(None, None, None), (None, None, "c"), (None, "b", None)],
)
async def test_get_credential_revocation_record_fail_bad_request(
    credential_exchange_id, credential_revocation_id, revocation_registry_id
):
    with pytest.raises(
        HTTPException,
        match="If credential_exchange_id is not provided then both "
        "credential_revocation_id and revocation_registry_id must be provided.",
    ) as exc:

        await get_credential_revocation_record(
            credential_exchange_id=credential_exchange_id,
            credential_revocation_id=credential_revocation_id,
            revocation_registry_id=revocation_registry_id,
            auth="mocked_auth",
        )

    assert exc.value.status_code == 400

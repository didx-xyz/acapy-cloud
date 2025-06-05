import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import TxnOrPublishRevocationsResult

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.issuer import PublishRevocationsRequest
from app.routes.revocation import publish_revocations
from app.tests.util.models.dummy_txn_record_publish import txn_record


@pytest.mark.anyio
@pytest.mark.parametrize(
    "publish_revocation_response",
    [None, TxnOrPublishRevocationsResult(txn=[txn_record])],
)
async def test_publish_revocations_success(publish_revocation_response):
    mock_aries_controller = AsyncMock()
    mock_publish_revocations = AsyncMock(return_value=publish_revocation_response)

    mock_get_transaction = AsyncMock()

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        patch(
            "app.services.revocation_registry.publish_pending_revocations",
            mock_publish_revocations,
        ),
        patch(
            "app.routes.revocation.coroutine_with_retry_until_value",
            mock_get_transaction,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        publish_request = PublishRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await publish_revocations(publish_request=publish_request, auth="mocked_auth")

        mock_publish_revocations.assert_awaited_once_with(
            controller=mock_aries_controller, revocation_registry_credential_map={}
        )
        if publish_revocation_response:
            mock_get_transaction.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (CloudApiException, 400, "Bad request"),
        (CloudApiException, 404, "Not found"),
        (CloudApiException, 500, "Internal Server Error"),
    ],
)
async def test_publish_revocations_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_publish_revocations = AsyncMock(
        side_effect=exception_class(
            status_code=expected_status_code, detail=expected_detail
        )
    )

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        pytest.raises(CloudApiException, match=expected_detail) as exc,
        patch(
            "app.services.revocation_registry.publish_pending_revocations",
            mock_publish_revocations,
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        publish_request = PublishRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await publish_revocations(publish_request=publish_request, auth="mocked_auth")

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_publish_revocations_fail_timeout():
    mock_aries_controller = AsyncMock()
    mock_publish_revocations = AsyncMock(
        return_value=TxnOrPublishRevocationsResult(txn=[txn_record])
    )

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        pytest.raises(
            CloudApiException,
            match="Timeout waiting for endorser to accept the revocations request.",
        ) as exc,
        patch(
            "app.services.revocation_registry.publish_pending_revocations",
            mock_publish_revocations,
        ),
        patch(
            "app.routes.revocation.coroutine_with_retry_until_value",
            AsyncMock(side_effect=asyncio.TimeoutError()),
        ),
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        publish_request = PublishRevocationsRequest(
            revocation_registry_credential_map={}
        )

        await publish_revocations(publish_request=publish_request, auth="mocked_auth")

    assert exc.value.status_code == 504

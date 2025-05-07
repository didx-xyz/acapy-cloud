from unittest.mock import AsyncMock, Mock, patch

import pytest
from aries_cloudcontroller import V20CredRequestRequest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.routes.issuer import request_credential
from app.services.issuer.acapy_issuer_v2 import IssuerV2


@pytest.mark.anyio
@pytest.mark.parametrize("record_type", ["anoncreds", "ld_proof", "bad"])
@pytest.mark.parametrize("save_exchange_record", [None, True, False])
async def test_request_credential_success(record_type, save_exchange_record):
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.request_credential = IssuerV2.request_credential

    record = Mock()
    record.type = record_type
    issuer.get_record = AsyncMock(return_value=record)

    mock_aries_controller.issue_credential_v2_0.send_request = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.IssuerV2", new=issuer
    ), patch(
        "app.routes.issuer.did_from_credential_definition_id", return_value="issuer_did"
    ), patch(
        "app.routes.issuer.qualified_did_sov", return_value="qualified_did_sov"
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ), patch(
        "app.services.issuer.acapy_issuer_v2.credential_record_to_model_v2"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if record_type == "bad":
            with pytest.raises(
                HTTPException, match="Unsupported credential type: bad"
            ) as exc:
                await request_credential(
                    credential_exchange_id="v2-test_id", auth="mocked_auth"
                )

            assert exc.value.status_code == 500

        else:
            await request_credential(
                credential_exchange_id="v2-test_id",
                save_exchange_record=save_exchange_record,
                auth="mocked_auth",
            )

            auto_remove = (
                not save_exchange_record if save_exchange_record is not None else None
            )
            mock_aries_controller.issue_credential_v2_0.send_request.assert_awaited_once_with(
                cred_ex_id="test_id",
                body=V20CredRequestRequest(auto_remove=auto_remove),
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
async def test_request_credential_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.request_credential = IssuerV2.request_credential

    record = Mock()
    record.type = "anoncreds"
    issuer.get_record = AsyncMock(return_value=record)

    mock_aries_controller.issue_credential_v2_0.send_request = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.issuer.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException, match=expected_detail
    ) as exc, patch(
        "app.routes.issuer.IssuerV2", new=issuer
    ), patch(
        "app.services.issuer.acapy_issuer_v2.credential_record_to_model_v2"
    ), patch(
        "app.routes.issuer.did_from_credential_definition_id", return_value="issuer_did"
    ), patch(
        "app.routes.issuer.qualified_did_sov", return_value="qualified_did_sov"
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await request_credential(
            credential_exchange_id="v2-test_id", auth="mocked_auth"
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_request_credential_fail_bad_record():
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.request_credential = IssuerV2.request_credential

    record = Mock()
    record.type = "anoncreds"
    record.credential_definition_id = None
    issuer.get_record = AsyncMock(return_value=record)

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.IssuerV2", new=issuer
    ), patch(
        "app.services.issuer.acapy_issuer_v2.credential_record_to_model_v2"
    ), pytest.raises(
        HTTPException,
        match=(
            "Record has no credential definition or schema associated. "
            "This probably means you haven't received an offer yet."
        ),
    ) as exc:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await request_credential(
            credential_exchange_id="v2-test_id", auth="mocked_auth"
        )

    assert exc.value.status_code == 412

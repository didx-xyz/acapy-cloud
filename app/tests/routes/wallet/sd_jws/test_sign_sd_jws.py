from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import SDJWSCreate
from pydantic import ValidationError

from app.exceptions import CloudApiException
from app.models.sd_jws import SDJWSCreateRequest
from app.routes.wallet.sd_jws import sign_sd_jws


@pytest.mark.anyio
async def test_sign_jws_success() -> None:
    sd_jws = (
        "eyJ0eXAiOiAiSldUIiwgImFsZyI6ICJFZERTQSIsICJraWQiOiAiZGlkOnNvdjpBR2d1UjRtYzE4NlR3MTFLZVdkNHFxI2"
        "tleS0xIn0.eyJ0ZXN0IjogInRlc3RfdmFsdWUifQ.3IxwPkA2niDxCsd12kDRVveR-aPBJx7YibWy9fbrFTSWbITQ16CqA0"
        "AR5_M4StTauO3_t063Mjno32O0wqcbDg"
    )
    mock_aries_controller = AsyncMock()
    mock_handle_acapy_call = AsyncMock()
    mock_handle_acapy_call.return_value = sd_jws
    request_body = SDJWSCreateRequest(
        did="did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6",
        payload={
            "sub": "6c5c0a49-b589-431d-bae7-219122a9ec2c",
            "given_name": "John",
            "family_name": "Doe",
            "email": "johndoe@example.com",
            "phone_number": "+1-202-555-0101",
            "address": {
                "street_address": "123 Main St",
                "locality": "Anytown",
                "region": "Anystate",
                "country": "US",
            },
            "birthdate": "1940-01-01",
        },
    )

    payload = SDJWSCreate(**request_body.model_dump())

    with (
        patch("app.routes.wallet.sd_jws.client_from_auth") as mock_client_from_auth,
        patch("app.routes.wallet.sd_jws.handle_acapy_call", mock_handle_acapy_call),
        patch("app.routes.wallet.sd_jws.logger") as mock_logger,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        result = await sign_sd_jws(body=request_body, auth="mocked_auth")

        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock_logger.bind(),
            acapy_call=mock_aries_controller.wallet.sign_sd_jwt,
            body=payload,
        )

        assert result.sd_jws == sd_jws


@pytest.mark.anyio
async def test_sign_jws_validation_error() -> None:
    error_msg = "Validation error message"

    request_body = SDJWSCreateRequest(
        did="did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6",
        payload={
            "sub": "6c5c0a49-b589-431d-bae7-219122a9ec2c",
            "given_name": "John",
            "family_name": "Doe",
            "email": "johndoe@example.com",
            "phone_number": "+1-202-555-0101",
            "address": {
                "street_address": "123 Main St",
                "locality": "Anytown",
                "region": "Anystate",
                "country": "US",
            },
            "birthdate": "1940-01-01",
        },
    )

    mock_validation_error = ValidationError.from_exception_data(
        title="ValidationError",
        line_errors=[
            {
                "loc": ("field",),
                "msg": "error message",
                "type": "value_error",
                "input": "invalid_input",
                "ctx": {"error": "some context"},
            }
        ],
    )

    with (
        patch("app.routes.wallet.sd_jws.SDJWSCreate") as mock_jws_create,
        patch("app.routes.wallet.sd_jws.logger") as mock_logger,
        patch(
            "app.routes.wallet.sd_jws.extract_validation_error_msg",
            return_value=error_msg,
        ),
    ):
        mock_jws_create.side_effect = mock_validation_error

        with pytest.raises(CloudApiException) as exc_info:
            await sign_sd_jws(body=request_body, auth="mocked_auth")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == error_msg

        mock_logger.bind.assert_called_once()
        mock_logger.bind().info.assert_called_once_with(
            "Bad request: Validation error from SDJWSCreateRequest body: {}", error_msg
        )

from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import JWSCreate
from pydantic import ValidationError

from app.exceptions import CloudApiException
from app.models.jws import JWSCreateRequest
from app.routes.wallet.jws import sign_jws


@pytest.mark.anyio
async def test_sign_jws_success():
    jws = (
        "eyJ0eXAiOiAiSldUIiwgImFsZyI6ICJFZERTQSIsICJraWQiOiAiZGlkOnNvdjpBR2d1UjRtYzE4NlR3MTFLZVdkNHFxI2"
        "tleS0xIn0.eyJ0ZXN0IjogInRlc3RfdmFsdWUifQ.3IxwPkA2niDxCsd12kDRVveR-aPBJx7YibWy9fbrFTSWbITQ16CqA0"
        "AR5_M4StTauO3_t063Mjno32O0wqcbDg"
    )

    mock_aries_controller = AsyncMock()
    mock_handle_acapy_call = AsyncMock()
    mock_handle_acapy_call.return_value = jws
    request_body = JWSCreateRequest(
        did="did:sov:AGguR4mc186Tw11KeWd4qq", payload={"test": "test_value"}
    )

    payload = JWSCreate(**request_body.model_dump())

    with (
        patch("app.routes.wallet.jws.client_from_auth") as mock_client_from_auth,
        patch("app.routes.wallet.jws.handle_acapy_call", mock_handle_acapy_call),
        patch("app.routes.wallet.jws.logger") as mock_logger,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        result = await sign_jws(body=request_body, auth="mocked_auth")

        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock_logger.bind(),
            acapy_call=mock_aries_controller.wallet.sign_jwt,
            body=payload,
        )

        assert result.jws == jws


@pytest.mark.anyio
async def test_sign_jws_validation_error():
    error_msg = "Validation error message"

    # Create a request that will trigger a ValidationError
    request_body = JWSCreateRequest(
        did="did:sov:AGguR4mc186Tw11KeWd4qq", payload={"test": "test_value"}
    )

    # Mock the JWSCreate to raise ValidationError
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
        patch("app.routes.wallet.jws.JWSCreate") as mock_jws_create,
        patch("app.routes.wallet.jws.logger") as mock_logger,
        patch(
            "app.routes.wallet.jws.extract_validation_error_msg", return_value=error_msg
        ),
    ):
        mock_jws_create.side_effect = mock_validation_error

        # Assert that the function raises CloudApiException with correct status code
        with pytest.raises(CloudApiException) as exc_info:
            await sign_jws(body=request_body, auth="mocked_auth")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == error_msg

        # Verify logging calls
        mock_logger.bind.assert_called_once()
        mock_logger.bind().info.assert_called_once_with(
            "Bad request: Validation error from JWSCreateRequest body: {}", error_msg
        )

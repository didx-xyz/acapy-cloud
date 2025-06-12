from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import JWSVerify
from pydantic import ValidationError

from app.exceptions import CloudApiException
from app.models.jws import JWSVerifyRequest, JWSVerifyResponse
from app.routes.wallet.jws import verify_jws


@pytest.mark.anyio
async def test_verify_jws_success():
    # Sample JWS string
    jws = (
        "eyJ0eXAiOiAiSldUIiwgImFsZyI6ICJFZERTQSIsICJraWQiOiAiZGlkOnNvdjpBR2d1UjRtYzE4NlR3MTFLZVdkNHFxI2"
        "tleS0xIn0.eyJ0ZXN0IjogInRlc3RfdmFsdWUifQ.3IxwPkA2niDxCsd12kDRVveR-aPBJx7YibWy9fbrFTSWbITQ16CqA0"
        "AR5_M4StTauO3_t063Mjno32O0wqcbDg"
    )

    # Mock response data
    verify_result_data = {
        "payload": {"test": "test_value"},
        "headers": {
            "typ": "JWT",
            "alg": "EdDSA",
            "kid": "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6#key-1",
        },
        "kid": "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6#key-1",
        "valid": True,
        "error": None,
    }

    mock_aries_controller = AsyncMock()
    mock_handle_acapy_call = AsyncMock()
    mock_verify_result = MagicMock()
    mock_verify_result.model_dump.return_value = verify_result_data
    mock_handle_acapy_call.return_value = mock_verify_result

    request_body = JWSVerifyRequest(jws=jws)
    verify_request = JWSVerify(jwt=request_body.jws)

    with (
        patch("app.routes.wallet.jws.client_from_auth") as mock_client_from_auth,
        patch("app.routes.wallet.jws.handle_acapy_call", mock_handle_acapy_call),
        patch("app.routes.wallet.jws.logger") as mock_logger,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        result = await verify_jws(body=request_body, auth="mocked_auth")

        # Assert the acapy call was made correctly
        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock_logger.bind(),
            acapy_call=mock_aries_controller.wallet.verify_jwt,
            body=verify_request,
        )

        # Assert the response matches expected data
        assert isinstance(result, JWSVerifyResponse)
        assert result.payload == verify_result_data["payload"]
        assert result.headers == verify_result_data["headers"]
        assert result.kid == verify_result_data["kid"]
        assert result.valid == verify_result_data["valid"]
        assert result.error == verify_result_data["error"]


@pytest.mark.anyio
async def test_verify_jws_validation_error():
    error_msg = "field required"
    modified_error_msg = error_msg.replace(
        "jwt", "jws"
    )  # Match the error message modification in the code

    # Create a request that will trigger a ValidationError
    request_body = JWSVerifyRequest(jws="invalid_jws")

    # Create a ValidationError with proper error data structure
    mock_validation_error = ValidationError.from_exception_data(
        title="ValidationError",
        line_errors=[
            {
                "loc": ("jwt",),
                "msg": error_msg,
                "type": "value_error",
                "input": "invalid_input",
                "ctx": {"error": "some context"},
            }
        ],
    )

    with (
        patch("app.routes.wallet.jws.JWSVerify") as mock_jws_verify,
        patch("app.routes.wallet.jws.logger") as mock_logger,
        patch(
            "app.routes.wallet.jws.extract_validation_error_msg", return_value=error_msg
        ),
    ):
        mock_jws_verify.side_effect = mock_validation_error

        # Assert that the function raises CloudApiException with correct status code
        with pytest.raises(CloudApiException) as exc_info:
            await verify_jws(body=request_body, auth="mocked_auth")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == modified_error_msg

        # Verify logging calls
        mock_logger.bind.assert_called_once()
        mock_logger.bind().info.assert_called_once_with(
            "Bad request: Validation error from JWSVerifyRequest body: {}",
            modified_error_msg,
        )

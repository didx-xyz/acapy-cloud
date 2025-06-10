from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import SDJWSVerify
from pydantic import ValidationError

from app.exceptions import CloudApiException
from app.models.sd_jws import SDJWSVerifyRequest, SDJWSVerifyResponse
from app.routes.wallet.sd_jws import verify_sd_jws


@pytest.mark.anyio
async def test_verify_jws_success():
    sd_jws = (
        "eyJ0eXAiOiAiSldUIiwgImFsZyI6ICJFZERTQSIsICJraWQiOiAiZGlkOnNvdjpBR2d1UjRtYzE4NlR3MTFLZVdkNHFxI2"
        "tleS0xIn0.eyJ0ZXN0IjogInRlc3RfdmFsdWUifQ.3IxwPkA2niDxCsd12kDRVveR-aPBJx7YibWy9fbrFTSWbITQ16CqA0"
        "AR5_M4StTauO3_t063Mjno32O0wqcbDg"
    )

    verify_result_data = {
        "error": None,
        "headers": {
            "typ": "JWT",
            "alg": "EdDSA",
            "kid": "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6#key-1",
        },
        "kid": "did:cheqd:testnet:39be08a4-8971-43ee-8a10-821ad52f24c6#key-1",
        "payload": {
            "_sd": [
                "EC11V8vqqgEzOa3AN8yVLXRxccwlvgsLnnE65sswodc",
                "L3qtnA4G4qPgeQRpQB-ElVjiVb359mUekdSthnlbSm4",
                "YM5B1pv75DyS-NrV9pp0MSjsQ-flZGWLRH4LIFIB-Ak",
                "_T5gi7uVTGnVYO-ZlCf1Kpi2hin6bbQEHVBcyc2Eoos",
                "c08PRylz5JC48qTKCS2gB8m8w5_rwdyR_21rU-Lihy4",
                "iCFc_OttaWX4-xyQKvtiap2lj23559F9L71dGRgxBtU",
                "jD2CdSZhoXqmWU8cLpVDO--jmGMUA9X69egNct1Fy3o",
            ],
            "_sd_alg": "sha-256",
        },
        "valid": True,
        "disclosures": [
            ["jSJmzgsBzr5FihgNN-c-cQ", "sub", "6c5c0a49-b589-431d-bae7-219122a9ec2c"],
            ["_NNXgraBDZ4sBj1FuHhR9A", "phone_number", "+1-202-555-0101"],
            ["eHyW2lNnhV6leIAKKknw1g", "given_name", "John"],
            ["W7_cQ9t7Ku51QsnmGs6N2Q", "family_name", "Doe"],
            ["ZXAQfGxkHJQW_710pAYBOQ", "email", "johndoe@example.com"],
            ["14nrze3QYl7kp9T6EMSVgA", "birthdate", "1940-01-01"],
            ["Sb_A9zLRuIM7GuqoifMxtg", "street_address", "123 Main St"],
            ["nVNPkPSS3LAegaMpxcdZug", "region", "Anystate"],
            ["qYjnqrWKte6xqch5i09ifQ", "locality", "Anytown"],
            ["XuUKAq8jhvviIa5NmUMvJg", "country", "US"],
            [
                "WkL3DTJPeIuOpYtI-o4O8w",
                "address",
                {
                    "_sd": [
                        "26rGNWx31pylSeigFTp9pgNknJEHugnQ2z2Dw61j4UU",
                        "FlZhssejmKlEuy_iCNYdaSlkNJA9WoANlQvGA6x7to4",
                        "su6kv3Dx1hurEcMAWTeRUY4uq70zhaQLu81132LYcyE",
                        "wVRA97TzcFLZGBzBDSAECSjdJ7TKVRSyuKxqtr6Hg_E",
                    ]
                },
            ],
        ],
    }

    mock_aries_controller = AsyncMock()
    mock_handle_acapy_call = AsyncMock()
    mock_verify_result = MagicMock()
    mock_verify_result.model_dump.return_value = verify_result_data
    mock_handle_acapy_call.return_value = mock_verify_result

    request_body = SDJWSVerifyRequest(sd_jws=sd_jws)
    verify_request = SDJWSVerify(sd_jwt=request_body.sd_jws)

    with (
        patch("app.routes.wallet.sd_jws.client_from_auth") as mock_client_from_auth,
        patch("app.routes.wallet.sd_jws.handle_acapy_call", mock_handle_acapy_call),
        patch("app.routes.wallet.sd_jws.logger") as mock_logger,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        result = await verify_sd_jws(body=request_body, auth="mocked_auth")

        # Assert the acapy call was made correctly
        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock_logger.bind(),
            acapy_call=mock_aries_controller.wallet.verify_sd_jwt,
            body=verify_request,
        )

        # Assert the response matches expected data
        assert isinstance(result, SDJWSVerifyResponse)
        assert result.payload == verify_result_data["payload"]
        assert result.headers == verify_result_data["headers"]
        assert result.kid == verify_result_data["kid"]
        assert result.valid == verify_result_data["valid"]
        assert result.error == verify_result_data["error"]
        assert result.disclosures == verify_result_data["disclosures"]


@pytest.mark.anyio
async def test_verify_jws_validation_error():
    error_msg = "field required"
    modified_error_msg = error_msg.replace("jwt", "jws")
    request_body = SDJWSVerifyRequest(sd_jws="invalid_sd_jws")

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
        patch("app.routes.wallet.sd_jws.SDJWSVerify") as mock_jws_verify,
        patch("app.routes.wallet.sd_jws.logger") as mock_logger,
        patch(
            "app.routes.wallet.sd_jws.extract_validation_error_msg",
            return_value=error_msg,
        ),
    ):
        mock_jws_verify.side_effect = mock_validation_error

        with pytest.raises(CloudApiException) as exc_info:
            await verify_sd_jws(body=request_body, auth="mocked_auth")

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == modified_error_msg

        mock_logger.bind.assert_called_once()
        mock_logger.bind().info.assert_called_once_with(
            "Bad request: Validation error from SDJWSVerifyRequest body: {}",
            modified_error_msg,
        )

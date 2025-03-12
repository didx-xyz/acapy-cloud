from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.issuer import CredentialType, SendCredential
from app.routes.issuer import send_credential
from app.tests.routes.issuer.test_create_offer import anoncreds_cred, indy_cred, ld_cred


@pytest.mark.anyio
@pytest.mark.parametrize(
    "credential",
    [
        SendCredential(
            type=CredentialType.INDY,
            indy_credential_detail=indy_cred,
            connection_id="abc",
        ),
        SendCredential(
            type=CredentialType.LD_PROOF,
            ld_credential_detail=ld_cred,
            connection_id="abc",
        ),
        SendCredential(
            type=CredentialType.ANONCREDS,
            anoncreds_credential_detail=anoncreds_cred,
            connection_id="abc",
        ),
    ],
)
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_send_credential_success(credential, wallet_type):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.issue_credential_automated = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.assert_public_did", return_value="public_did"
    ), patch(
        "app.services.issuer.acapy_issuer_v2.credential_record_to_model_v2"
    ), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ), patch(
        "app.routes.issuer.get_wallet_type", return_value=wallet_type
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if (
            credential.type is CredentialType.ANONCREDS
            and wallet_type != "askar-anoncreds"
        ):
            with pytest.raises(CloudApiException) as exc:
                await send_credential(credential=credential, auth="mocked_auth")
            assert exc.value.status_code == 400
            assert (
                exc.value.detail
                == "AnonCreds credentials can only be issued by an askar-anoncreds wallet"
            )
        else:
            await send_credential(credential=credential, auth="mocked_auth")

            mock_aries_controller.issue_credential_v2_0.issue_credential_automated.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_send_credential_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.issue_credential_automated = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.issuer.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException, match=expected_detail
    ) as exc, patch(
        "app.routes.issuer.assert_public_did", return_value="public_did"
    ), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ), patch(
        "app.routes.issuer.get_wallet_type", return_value="askar"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await send_credential(
            credential=SendCredential(
                type=CredentialType.INDY,
                indy_credential_detail=indy_cred,
                connection_id="abc",
            ),
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_send_credential_fail_bad_public_did():
    credential = SendCredential(
        type=CredentialType.INDY,
        indy_credential_detail=indy_cred,
        connection_id="abc",
    )

    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.issue_credential_automated = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.assert_public_did",
        AsyncMock(side_effect=CloudApiException(status_code=404, detail="Not found")),
    ), pytest.raises(
        HTTPException,
        match="Wallet making this request has no public DID. Only issuers with a public DID can make this request.",
    ) as exc:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await send_credential(credential=credential, auth="mocked_auth")

        mock_aries_controller.issue_credential_v2_0.issue_credential_automated.assert_awaited_once()

    assert exc.value.status_code == 403

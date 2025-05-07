from unittest.mock import AsyncMock, Mock, patch

import pytest
from aries_cloudcontroller import Credential, LDProofVCDetail, LDProofVCOptions
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)
from fastapi import HTTPException

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.issuer import AnonCredsCredential, CreateOffer
from app.routes.issuer import create_offer

ld_cred = LDProofVCDetail(
    credential=Credential(
        context=[
            "https://www.w3.org/2018/credentials/v1",
            "https://www.w3.org/2018/credentials/examples/v1",
        ],
        type=["VerifiableCredential", "UniversityDegreeCredential"],
        credentialSubject={
            "degree": {
                "type": "BachelorDegree",
                "name": "Bachelor of Science and Arts",
            },
            "college": "Faber College",
        },
        issuanceDate="2021-04-12",
        issuer="",
    ),
    options=LDProofVCOptions(proofType="Ed25519Signature2018"),
)
anoncreds_cred = AnonCredsCredential(
    issuer_did="WgWxqztrNooG92RXvxSTWv",
    credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
    attributes={},
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "credential",
    [
        CreateOffer(
            ld_credential_detail=ld_cred,
        ),
        CreateOffer(
            anoncreds_credential_detail=anoncreds_cred,
        ),
    ],
)
@pytest.mark.parametrize("wallet_type", ["askar-anoncreds"])
async def test_create_offer_success(credential, wallet_type):
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.create_offer = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.IssuerV2", new=issuer
    ), patch(
        "app.util.valid_issuer.assert_public_did", return_value="public_did"
    ), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ), patch(
        "app.util.valid_issuer.get_wallet_type", return_value=wallet_type
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if (
            credential.get_credential_type() == "anoncreds"
            and wallet_type != "askar-anoncreds"
        ):
            with pytest.raises(CloudApiException) as exc:
                await create_offer(credential=credential, auth="mocked_auth")
            assert exc.value.status_code == 400
            assert (
                exc.value.detail
                == "AnonCreds credentials can only be issued by an askar-anoncreds wallet"
            )
        else:
            await create_offer(credential=credential, auth="mocked_auth")

            issuer.create_offer.assert_awaited_once_with(
                controller=mock_aries_controller, credential=credential
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
async def test_create_offer_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.create_offer = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with patch(
        "app.routes.issuer.client_from_auth"
    ) as mock_client_from_auth, pytest.raises(
        HTTPException, match=expected_detail
    ) as exc, patch(
        "app.util.valid_issuer.assert_public_did", return_value="public_did"
    ), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ), patch(
        "app.util.valid_issuer.get_wallet_type", return_value="askar"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_offer(
            credential=CreateOffer(
                ld_credential_detail=ld_cred,
            ),
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_create_offer_fail_bad_public_did():
    credential = CreateOffer(anoncreds_credential_detail=anoncreds_cred)

    mock_aries_controller = AsyncMock()
    mock_aries_controller.issue_credential_v2_0.issue_credential_automated = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.util.valid_issuer.assert_public_did",
        AsyncMock(side_effect=CloudApiException(status_code=404, detail="Not found")),
    ), pytest.raises(
        HTTPException,
        match="Wallet making this request has no public DID. Only issuers with a public DID can make this request.",
    ) as exc:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_offer(credential=credential, auth="mocked_auth")

        mock_aries_controller.issue_credential_v2_0.issue_credential_automated.assert_awaited_once()

    assert exc.value.status_code == 403

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
from app.models.issuer import CreateOffer, CredentialType, IndyCredential
from app.routes.issuer import create_offer

indy_cred = IndyCredential(
    credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag", attributes={}
)
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "credential",
    [
        CreateOffer(
            protocol_version="v2",
            type=CredentialType.INDY,
            indy_credential_detail=indy_cred,
        ),
        CreateOffer(
            protocol_version="v2",
            type=CredentialType.LD_PROOF,
            ld_credential_detail=ld_cred,
        ),
    ],
)
async def test_create_offer_success(credential):
    mock_aries_controller = AsyncMock()
    issuer = Mock()
    issuer.create_offer = AsyncMock()

    with patch("app.routes.issuer.client_from_auth") as mock_client_from_auth, patch(
        "app.routes.issuer.issuer_from_protocol_version",
        return_value=issuer,
    ), patch("app.routes.issuer.assert_public_did", return_value="public_did"), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

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
        "app.routes.issuer.assert_public_did", return_value="public_did"
    ), patch(
        "app.routes.issuer.schema_id_from_credential_definition_id",
        return_value="schema_id",
    ), patch(
        "app.routes.issuer.assert_valid_issuer"
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_offer(
            credential=CreateOffer(
                protocol_version="v2",
                type=CredentialType.LD_PROOF,
                ld_credential_detail=ld_cred,
            ),
            auth="mocked_auth",
        )

    assert exc.value.status_code == expected_status_code


@pytest.mark.anyio
async def test_create_offer_fail_bad_public_did():
    credential = CreateOffer(
        protocol_version="v2",
        type=CredentialType.INDY,
        indy_credential_detail=indy_cred,
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

        await create_offer(credential=credential, auth="mocked_auth")

        mock_aries_controller.issue_credential_v2_0.issue_credential_automated.assert_awaited_once()

    assert exc.value.status_code == 403

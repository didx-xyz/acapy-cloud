import pytest
from aries_cloudcontroller import Credential, LDProofVCDetail, LDProofVCOptions

from app.models.issuer import (
    AnonCredsCredential,
    CredentialBase,
)
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_credential_base_model():
    # valid ld_proof
    CredentialBase(
        ld_credential_detail=LDProofVCDetail(
            credential=Credential(
                context=[],
                credentialSubject={},
                issuanceDate="2024-04-18",
                issuer="abc",
                type=[],
            ),
            options=LDProofVCOptions(proofType="Ed25519Signature2018"),
        ),
    )

    # valid anoncreds
    CredentialBase(
        anoncreds_credential_detail=AnonCredsCredential(
            issuer_did="WgWxqztrNooG92RXvxSTWv",
            credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
            attributes={},
        ),
    )

    # both details are None
    with pytest.raises(CloudApiValueError) as exc:
        CredentialBase(ld_credential_detail=None, anoncreds_credential_detail=None)
    assert exc.value.detail == (
        "One of anoncreds_credential_detail or ld_credential_detail must be populated"
    )

    # both details are populated
    with pytest.raises(CloudApiValueError) as exc:
        CredentialBase(
            ld_credential_detail=LDProofVCDetail(
                credential=Credential(
                    context=[],
                    credentialSubject={},
                    issuanceDate="2024-04-18",
                    issuer="abc",
                    type=[],
                ),
                options=LDProofVCOptions(proofType="Ed25519Signature2018"),
            ),
            anoncreds_credential_detail=AnonCredsCredential(
                issuer_did="WgWxqztrNooG92RXvxSTWv",
                credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
                attributes={},
            ),
        )
    assert exc.value.detail == (
        "Only one of anoncreds_credential_detail or ld_credential_detail must be populated"
    )

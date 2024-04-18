import pytest
from aries_cloudcontroller import Credential, LDProofVCDetail, LDProofVCDetailOptions

from app.models.issuer import CredentialBase, CredentialType, IndyCredential
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_credential_base_model():
    CredentialBase(  # valid indy
        indy_credential_detail=IndyCredential(
            credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag",
            attributes={},
        )
    )

    CredentialBase(  # valid ld_proof
        type=CredentialType.LD_PROOF,
        ld_credential_detail=LDProofVCDetail(
            credential=Credential(
                context=[],
                credentialSubject={},
                issuanceDate="2024-04-18",
                issuer="abc",
                type=[],
            ),
            options=LDProofVCDetailOptions(proofType="Ed25519Signature2018"),
        ),
    )

    with pytest.raises(CloudApiValueError) as exc:
        CredentialBase(type=CredentialType.INDY, indy_credential_detail=None)
    assert exc.value.detail == (
        "indy_credential_detail must be populated if `indy` "
        "credential type is selected"
    )

    with pytest.raises(CloudApiValueError) as exc:
        CredentialBase(type=CredentialType.LD_PROOF, ld_credential_detail=None)
    assert exc.value.detail == (
        "ld_credential_detail must be populated if `ld_proof` "
        "credential type is selected"
    )

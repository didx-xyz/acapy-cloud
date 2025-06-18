import pytest
from aries_cloudcontroller import SignatureOptions

from app.models.jsonld import JsonLdSignRequest, JsonLdVerifyRequest
from shared.exceptions.cloudapi_value_error import CloudApiValueError

signature_options = SignatureOptions(
    proof_purpose="test", verification_method="ed25519"
)


def test_json_ld_sign_request():
    # Valid:
    JsonLdSignRequest(
        credential_id="abc",
        signature_options=signature_options,
    )

    # Only of credential or credential_id must be populated
    with pytest.raises(CloudApiValueError) as exc:
        JsonLdSignRequest(
            credential=None,
            credential_id=None,
            signature_options=signature_options,
        )
    assert exc.value.detail == (
        "At least one of `credential` or `credential_id` must be provided."
    )

    # Only one of verkey or pub_did should be provided
    with pytest.raises(CloudApiValueError) as exc:
        JsonLdSignRequest(
            verkey="abc",
            pub_did="abc",
            signature_options=signature_options,
        )
    assert exc.value.detail == (
        "Please provide either or neither, but not both, "
        "the pub_did or the verkey for the document."
    )


def test_json_ld_verify_request():
    # Valid:
    JsonLdVerifyRequest(doc={}, verkey="abc", public_did=None)

    # Only one of verkey or pub_did should be provided
    with pytest.raises(CloudApiValueError) as exc:
        JsonLdVerifyRequest(doc={}, verkey="abc", public_did="abc")
    assert exc.value.detail == (
        "Please provide either or neither, but not both, "
        "the public_did or the verkey for the document."
    )

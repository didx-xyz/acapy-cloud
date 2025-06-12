import pytest
from aries_cloudcontroller import AcaPyClient, SignatureOptions
from fastapi import HTTPException

from app.models.jsonld import JsonLdSignRequest, JsonLdVerifyRequest
from app.routes.jsonld import router
from shared import RichAsyncClient
from shared.exceptions.cloudapi_value_error import CloudApiValueError
from shared.models.credential_exchange import CredentialExchange

JSONLD_BASE_PATH = router.prefix

jsonld_credential = {
    "@context": "https://json-ld.org/contexts/person.jsonld",
    "@id": "https://dbpedia.org/resource/John_Lennon",
    "name": "John Lennon",
    "born": "1940-10-09",
    "spouse": "https://dbpedia.org/resource/Cynthia_Lennon",
}

signed_doc = {
    "doc": {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://www.w3.org/2018/credentials/examples/v1",
        ],
        "id": "https://example.edu/credentials/1872",
        "type": ["VerifiableCredential", "AlumniCredential"],
        "issuanceDate": "2010-01-01T19:23:24Z",
        "credentialSubject": {
            "id": "did:example:ebfeb1f712ebc6f1c276e12ec21",
            "alumniOf": {
                "id": "did:example:c276e12ec21ebfeb1f712ebc6f1",
                "name": [
                    {"value": "Example University", "lang": "en"},
                    {"value": "Exemple d'Université", "lang": "fr"},
                ],
            },
        },
        "proof": {
            "type": "Ed25519Signature2018",
            "verificationMethod": "did:key:did:key:z6Mkq8pevWDaxgsD2DZC11JUnnjGdrLmHSh9P7waX3HR4Zwz"
            "#did:key:z6Mkq8pevWDaxgsD2DZC11JUnnjGdrLmHSh9P7waX3HR4Zwz",
            "proofPurpose": "assertionMethod",
            "created": "2022-11-24T08:20:11Z",
            "jws": "eyJhbGciOiAiRWREU0EiLCAiYjY0IjogZmFsc2UsICJjcml0IjogWyJiNjQiXX0..Rdpq5uOCJInEMD-"
            "5G7mXalu0NiJHSgIfE5ISE7Ed451wJmkpFHR50K9Sb3nEo0P8wpXzrUQRCETqImTvqsZNDA",
        },
    },
    "verkey": "BgZcLFy9d9NjuiiVKSLdwhBGpH4usZSnh72egmKQ9MAc",
}


@pytest.mark.anyio
@pytest.mark.xfail(
    reason="json-ld.org can be unresolvable, causing test failure.", strict=False
)
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_sign_jsonld(
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_client: RichAsyncClient,
    issue_anoncreds_credential_to_alice: CredentialExchange,
) -> None:
    # First assert 422 error for providing both pub_did and verkey:
    credential_id = issue_anoncreds_credential_to_alice["credential_exchange_id"][3:]
    with pytest.raises(CloudApiValueError) as exc:
        JsonLdSignRequest(
            verkey="abcde",
            pub_did="abcde",
            credential_id=credential_id,
            signature_options=SignatureOptions(
                proof_purpose="test", verification_method="ed25519"
            ).model_dump(),
        )

    assert "Please provide either or neither, but not both" in exc.value.detail

    # Success pub_did
    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did

    json_ld_req = JsonLdSignRequest(
        verkey=None,
        pub_did=faber_pub_did,
        credential=jsonld_credential,
        credential_id=None,
        signature_options=SignatureOptions(
            proof_purpose="test", verification_method="ed25519"
        ),
    )

    jsonld_sign_response = await faber_anoncreds_client.post(
        JSONLD_BASE_PATH + "/sign", json=json_ld_req.model_dump()
    )
    assert jsonld_sign_response.status_code == 200

    jsonld_sign_response = jsonld_sign_response.json()
    assert jsonld_sign_response["signed_doc"]
    assert all(item in jsonld_sign_response["signed_doc"] for item in jsonld_credential)

    # # Success verkey
    pub_did = (await faber_anoncreds_acapy_client.wallet.get_public_did()).result.did
    faber_verkey = (
        await faber_anoncreds_acapy_client.ledger.get_did_verkey(did=pub_did)
    ).verkey
    json_ld_req.pub_did = None
    json_ld_req.verkey = faber_verkey

    jsonld_sign_response = await faber_anoncreds_client.post(
        JSONLD_BASE_PATH + "/sign", json=json_ld_req.model_dump()
    )

    assert jsonld_sign_response.status_code == 200
    jsonld_sign_response = jsonld_sign_response.json()
    assert jsonld_sign_response["signed_doc"]
    assert all(item in jsonld_sign_response["signed_doc"] for item in jsonld_credential)

    # Success bare
    json_ld_req.pub_did = None
    json_ld_req.verkey = None

    jsonld_sign_response = await faber_anoncreds_client.post(
        JSONLD_BASE_PATH + "/sign", json=json_ld_req.model_dump()
    )

    assert jsonld_sign_response.status_code == 200
    jsonld_sign_response = jsonld_sign_response.json()
    assert jsonld_sign_response["signed_doc"]
    assert all(item in jsonld_sign_response["signed_doc"] for item in jsonld_credential)


@pytest.mark.skip("Model validation is overly strict again. To be reviewed")
@pytest.mark.anyio
@pytest.mark.xdist_group(name="issuer_test_group")
async def test_verify_jsonld(
    alice_member_client: RichAsyncClient,
    faber_anoncreds_acapy_client: AcaPyClient,
    faber_anoncreds_client: RichAsyncClient,
) -> None:
    jsonld_verify = JsonLdVerifyRequest(
        public_did="abcde",
        verkey=signed_doc["verkey"],
        doc=signed_doc["doc"],
    )
    # Error wrong args
    with pytest.raises(HTTPException) as exc:
        await alice_member_client.post(
            JSONLD_BASE_PATH + "/verify", json=jsonld_verify.model_dump()
        )
    assert (
        "Please provide either, but not both, public did of the verkey or the verkey for the document"
        in exc.value.detail
    )
    assert exc.value.status_code == 400

    # # Error invalid
    jsonld_verify.verkey = None
    faber_pub_did = (
        await faber_anoncreds_acapy_client.wallet.get_public_did()
    ).result.did
    jsonld_verify.public_did = faber_pub_did

    with pytest.raises(HTTPException) as exc:
        await faber_anoncreds_client.post(
            JSONLD_BASE_PATH + "/verify", json=jsonld_verify.model_dump()
        )

    assert exc.value.status_code == 422
    assert "Failed to verify payload" in exc.value.detail

    # Success
    jsonld_verify.public_did = None
    jsonld_verify.verkey = signed_doc["verkey"]

    response = await alice_member_client.post(
        JSONLD_BASE_PATH + "/verify", json=jsonld_verify.model_dump()
    )
    assert response.status_code == 204

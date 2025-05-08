from aries_cloudcontroller import Credential, LDProofVCDetail, LDProofVCOptions

from app.models.issuer import SendCredential


def create_credential(proof_type: str) -> dict:
    return SendCredential(
        connection_id="",
        ld_credential_detail=LDProofVCDetail(
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
            options=LDProofVCOptions(proofType=proof_type),
        ),
    ).model_dump(by_alias=True, exclude_unset=True)

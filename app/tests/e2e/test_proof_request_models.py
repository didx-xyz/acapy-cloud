import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    V10PresentationSendRequestRequest,
    V20PresRequestByFormat,
    V20PresSendRequestRequest,
)
from fastapi import HTTPException

from app.routes.verifier import router as verifier_router
from app.tests.util.connections import AcmeAliceConnect
from app.tests.util.webhooks import check_webhook_state
from shared.models.credential_exchange import CredentialExchange
from shared.util.rich_async_client import RichAsyncClient

VERIFIER_BASE_PATH = verifier_router.prefix


@pytest.mark.anyio
@pytest.mark.xfail(
    raises=HTTPException,
    strict=True,
    reason="Assert version and name are required fields, despite being optional according to ACA-Py models",
)
@pytest.mark.parametrize(
    "name, version, protocol_version",
    [
        ("Proof", None, "v1"),
        (None, "1.0", "v1"),
        (None, None, "v1"),
        ("Proof", None, "v2"),
        (None, "1.0", "v2"),
        (None, None, "v2"),
    ],
)
async def test_proof_model_failures(
    issue_credential_to_alice: CredentialExchange,  # pylint: disable=unused-argument
    acme_acapy_client: AcaPyClient,
    acme_and_alice_connection: AcmeAliceConnect,
    alice_member_client: RichAsyncClient,
    name: str,
    version: str,
    protocol_version: str,
):
    acme_connection_id = acme_and_alice_connection.acme_connection_id

    if protocol_version == "v1":

        request_body = V10PresentationSendRequestRequest(
            auto_remove=False,
            connection_id=acme_connection_id,
            comment="Test proof",
            proof_request={
                "name": name,
                "version": version,
                "requested_attributes": {
                    "THE_SPEED": {
                        "name": "speed",
                        "restrictions": [],
                    }
                },
                "requested_predicates": {},
            },
            auto_verify=True,
        )

        await acme_acapy_client.present_proof_v1_0.send_request_free(body=request_body)
    else:
        request_body = V20PresSendRequestRequest(
            auto_remove=False,
            connection_id=acme_connection_id,
            comment="Test proof",
            presentation_request=V20PresRequestByFormat(
                indy={
                    "name": name,
                    "version": version,
                    "requested_attributes": {
                        "THE_SPEED": {
                            "name": "speed",
                            "restrictions": [],
                        }
                    },
                    "requested_predicates": {},
                },
            ),
            auto_verify=True,
        )

        await acme_acapy_client.present_proof_v2_0.send_request_free(body=request_body)

    await check_webhook_state(
        client=alice_member_client,
        topic="proofs",
        state="request-received",
        look_back=5,
    )

    # Get proof exchange id
    alice_proof_exchange_id = (
        await alice_member_client.get(f"{VERIFIER_BASE_PATH}/proofs")
    ).json()[0]["proof_id"]

    # Get referent
    referent = (
        await alice_member_client.get(
            f"{VERIFIER_BASE_PATH}/proofs/{alice_proof_exchange_id}/credentials"
        )
    ).json()[0]["cred_info"]["referent"]

    # Accept proof request. This call will fail because the proof request is missing
    # the required fields (name and version). The send proof request call are missing
    # the required fields (name and version) and the ACA-Py models do not enforce these
    await alice_member_client.post(
        f"{VERIFIER_BASE_PATH}/accept-request",
        json={
            "proof_id": alice_proof_exchange_id,
            "type": "indy",
            "indy_presentation_spec": {
                "requested_attributes": {
                    "THE_SPEED": {"cred_id": referent, "revealed": True}
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
            "dif_presentation_spec": {},
        },
    )

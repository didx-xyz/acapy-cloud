from aries_cloudcontroller import Doc, SignRequest, SignResponse, VerifyRequest
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException, handle_acapy_call
from app.models.jsonld import JsonLdSignRequest, JsonLdVerifyRequest
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/jsonld", tags=["jsonld"])


@router.post("/sign")
async def sign_jsonld(
    body: JsonLdSignRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> SignResponse:
    """Sign a JSON-LD structure"""
    bound_logger = logger.bind(
        # Do not log credential data:
        body=body.model_dump(exclude="credential")
    )
    bound_logger.debug("POST request received: Sign JsonLD")

    async with client_from_auth(auth) as aries_controller:
        if body.verkey:
            verkey = body.verkey
        else:
            if body.pub_did:
                pub_did = body.pub_did
            else:
                bound_logger.debug("Fetching public DID")
                did_response = await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=aries_controller.wallet.get_public_did,
                )

                if not did_response.result or not did_response.result.did:
                    raise CloudApiException(
                        "Client requires a public did if verkey is not provided.", 400
                    )
                pub_did = did_response.result.did

            bound_logger.debug("Fetching verkey for DID")
            verkey_response = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.ledger.get_did_verkey,
                did=pub_did,
            )
            verkey = verkey_response.verkey
            if not verkey:
                raise CloudApiException(
                    "verkey was not provided and could not be obtained from the pub_did.",
                    500,
                )

        if not body.credential:
            if body.credential_id:
                # Can this ever be correct as in are there jsonLD credential potentially being returned?
                bound_logger.debug("Fetching credential from wallet")
                cred_info = await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=aries_controller.credentials.get_record,
                    credential_id=body.credential_id,
                )
                credential = cred_info.to_dict()
            else:
                # This is already handled in JsonLdSignRequest model validation
                raise CloudApiException(
                    "Neither a credential nor a credential ID is provided.", 400
                )
        else:
            credential = body.credential

        bound_logger.debug("Signing JsonLD")
        request_body = SignRequest(
            doc=Doc(credential=credential, options=body.signature_options),
            verkey=verkey,
        )
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.jsonld.sign,
            body=request_body,
        )
    if result:
        bound_logger.debug("Successfully signed JsonLD.")
    else:
        bound_logger.warning("No result from signing JsonLD.")
    return result


@router.post("/verify", status_code=204)
async def verify_jsonld(
    body: JsonLdVerifyRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """Verify a JSON-LD structure"""
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Verify JsonLD")

    async with client_from_auth(auth) as aries_controller:
        if not body.verkey:
            bound_logger.debug("Fetching verkey for DID")
            verkey_response = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.ledger.get_did_verkey,
                did=body.public_did,
            )
            verkey = verkey_response.verkey
            if not verkey:
                raise CloudApiException(
                    "verkey was not provided and could not be obtained from the pub_did.",
                    500,
                )
        else:
            verkey = body.verkey

        bound_logger.debug("Verifying JsonLD")
        request_body = VerifyRequest(doc=body.doc, verkey=verkey)
        jsonld_verify_response = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.jsonld.verify,
            body=request_body,
        )
        if not jsonld_verify_response.valid:
            raise CloudApiException(
                f"Failed to verify payload with error message: `{jsonld_verify_response.error}`.",
                422,
            )

    bound_logger.debug("Successfully verified JsonLD.")

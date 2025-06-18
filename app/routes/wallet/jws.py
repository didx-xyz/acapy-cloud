from aries_cloudcontroller import JWSCreate, JWSVerify
from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException, handle_acapy_call
from app.models.jws import (
    JWSCreateRequest,
    JWSCreateResponse,
    JWSVerifyRequest,
    JWSVerifyResponse,
)
from app.util.extract_validation_error import extract_validation_error_msg
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/wallet/jws", tags=["wallet"])


@router.post(
    "/sign",
    summary="Sign JWS",
)
async def sign_jws(
    body: JWSCreateRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> JWSCreateResponse:
    """Sign a JSON Web Signature (JWS).
    ---

    This endpoint allows users to sign a JSON payload, creating a JWS,
    using either a DID or a specific verification method.

    **Usage:**

    - **DID-Based Signing:** Provide the `did` field with a valid DID.
    The Aries agent will automatically select the appropriate verification key associated with the DID.

    - **Verification Method-Based Signing:** Provide the `verification_method` field with a specific verification method
    (DID with a verkey) to explicitly specify which key to use for signing.

    **Notes:**

    - The `header` field is optional. While you can specify custom headers, the `typ`, `alg`,
      and `kid` fields are automatically populated by the Aries agent based on the signing method.

    Example request body:
    ```json
    {
        "did": "did:cheqd:...",
        "payload": {
            "credential_subject": "reference_to_holder",
            "name": "Alice",
            "surname": "Demo"
        }
    }
    ```
    **OR**
    ```json
    {
        "payload": {
            "subject": "reference_to_holder",
            "name": "Alice",
            "surname": "Demo"
        },
        "verification_method": "did:key:z6Mkprf81ujG1n48n5LMD...M6S3#z6Mkprf81ujG1n48n5LMDaxyCLLFrnqCRBPhkTWsPfA8M6S3"
    }
    ```

    Request Body:
    ---
        JWSCreateRequest:
            `did` (str, optional): The DID to sign the JWS with.
            `verification_method` (str, optional): The verification method (DID with verkey) to use for signing.
            `payload` (dict): The JSON payload to be signed.
            `headers` (dict, optional): Custom headers for the JWS.

    Response:
    ---
        JWSCreateResponse:
            `jws` (str): The resulting JWS string representing the signed JSON Web Signature.

    **References:**

    - [JSON Web Signature (JWS) Specification](https://www.rfc-editor.org/rfc/rfc7515.html)
    """
    bound_logger = logger.bind(
        # Do not log payload:
        body=body.model_dump(exclude={"payload"})
    )
    bound_logger.debug("POST request received: Sign JWS")

    try:
        sign_request = JWSCreate(**body.model_dump())
    except ValidationError as e:
        # Handle Pydantic validation error:
        error_msg = extract_validation_error_msg(e)
        bound_logger.info(
            "Bad request: Validation error from JWSCreateRequest body: {}", error_msg
        )
        raise CloudApiException(status_code=422, detail=error_msg) from e

    async with client_from_auth(auth) as aries_controller:
        jws = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.wallet.sign_jwt,
            body=sign_request,
        )

    result = JWSCreateResponse(jws=jws)
    bound_logger.debug("Successfully signed JWS.")
    return result


@router.post(
    "/verify",
    summary="Verify JWS",
)
async def verify_jws(
    body: JWSVerifyRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> JWSVerifyResponse:
    """Verify a JSON Web Signature (JWS)
    ---

    This endpoint allows users to verify the authenticity and integrity of a JWS string previously generated
    by the /sign endpoint. It decodes the JWS to retrieve the payload and headers and assesses its validity.

    Request Body:
    ---
        JWSVerifyRequest: The JWS to verify.
            jws: str

    Returns
    -------
        JWSVerifyResponse
            payload: dict:
              The payload of the JWS.
            headers: dict:
              The headers of the JWS.
            kid: str:
              The key id of the signer.
            valid: bool:
              Whether the JWS is valid.
            error: str:
              The error message if the JWS is invalid.

    **References:**

    - [JSON Web Signature (JWS) Specification](https://www.rfc-editor.org/rfc/rfc7515.html)

    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Verify JWS")

    try:
        verify_request = JWSVerify(jwt=body.jws)
    except ValidationError as e:
        # Handle Pydantic validation error:
        error_msg = extract_validation_error_msg(e)
        error_msg = error_msg.replace("jwt", "jws")  # match the input field
        bound_logger.info(
            "Bad request: Validation error from JWSVerifyRequest body: {}", error_msg
        )
        raise CloudApiException(status_code=422, detail=error_msg) from e

    async with client_from_auth(auth) as aries_controller:
        verify_result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.wallet.verify_jwt,
            body=verify_request,
        )

    result = JWSVerifyResponse(**verify_result.model_dump())
    bound_logger.debug("Successfully verified JWS.")
    return result

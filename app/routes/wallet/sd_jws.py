from aries_cloudcontroller import SDJWSCreate, SDJWSVerify
from fastapi import APIRouter, Depends
from pydantic import ValidationError

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException, handle_acapy_call
from app.models.sd_jws import (
    SDJWSCreateRequest,
    SDJWSCreateResponse,
    SDJWSVerifyRequest,
    SDJWSVerifyResponse,
)
from app.util.extract_validation_error import extract_validation_error_msg
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/wallet/sd-jws", tags=["wallet"])


@router.post(
    "/sign",
    summary="Sign SD-JWS",
)
async def sign_sd_jws(
    body: SDJWSCreateRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> SDJWSCreateResponse:
    """Sign a Selective Disclosure JSON Web Signature (SD-JWS).
    ---

    This endpoint allows users to create a Selective Disclosure JSON Web Signature (SD-JWS).
    The SD-JWS enables the selective disclosure of specific attributes to a verifier while keeping others confidential.

    **Usage:**

    - **DID-Based Signing:** Provide the `did` field with a valid DID.
    The Aries agent will automatically select the appropriate verification key associated with the DID.

    - **Verification Method-Based Signing:** Provide the `verification_method` field with a specific verification method
    (DID with verkey) to explicitly specify which key to use for signing.

    **Notes:**

    - The `headers` field is optional. Custom headers can be specified, but the `typ`, `alg`,
      and `kid` fields are automatically populated by the Aries agent based on the signing method.
    - The `non_sd_list` field specifies attributes that are **not** selectively disclosed.
      Attributes listed here will always be included in the SD-JWS.

    **Non-Selective Disclosure (`non_sd_list`):**

    - To exclude list elements:
        - Use the format `"<attribute_name>[start:end]"` where `start` and `end` define the range
          (e.g., `"nationalities[1:3]"`).
    - To exclude specific dictionary attributes:
        - Use the format `"<dictionary_name>.<attribute_name>"` (e.g., `"address.street_address"`).

    **Example Request Body:**
    ```json
    {
        "did": "did:cheqd:...",
        "payload": {
            "credential_subject": "reference_to_holder",
            "given_name": "John",
            "family_name": "Doe",
            "email": "johndoe@example.com",
            "phone_number": "+27-123-4567",
            "nationalities": ["a","b","c","d"],
            "address": {
                "street_address": "123 Main St",
                "locality": "Anytown",
                "region": "Anywhere",
                "country": "ZA"
            },
            "birthdate": "1940-01-01"
        },
        "non_sd_list": [
            "given_name",
            "address",
            "address.street_address",
            "nationalities",
            "nationalities[1:3]"
        ]
    }
    ```

    Request Body:
    ---
        SDJWSCreateRequest:
            `did` (str, optional): The DID to sign the SD-JWS with.
            `verification_method` (str, optional): The verification method (DID with verkey) to use for signing.
            `payload` (dict): The JSON payload to be signed.
            `headers` (dict, optional): Custom headers for the SD-JWS.
            `non_sd_list` (List[str], optional): List of attributes excluded from selective disclosure.

    Response:
    ---
        SDJWSCreateResponse:
            `sd_jws` (str): The resulting SD-JWS string concatenated with the necessary disclosures in the format
            `<Issuer-signed JWS>~<Disclosure 1>~<Disclosure 2>~...~<Disclosure N>`.

    **References:**

    - [Selective Disclosure JSON Web Token (SD-JWT)
      Specification](https://www.ietf.org/archive/id/draft-ietf-oauth-selective-disclosure-jwt-07.html)
    """
    bound_logger = logger.bind(
        # Do not log payload:
        body=body.model_dump(exclude={"payload"})
    )
    bound_logger.debug("POST request received: Sign SD-JWS")

    try:
        sign_request = SDJWSCreate(**body.model_dump())
    except ValidationError as e:
        # Handle Pydantic validation error:
        error_msg = extract_validation_error_msg(e)
        bound_logger.info(
            "Bad request: Validation error from SDJWSCreateRequest body: {}", error_msg
        )
        raise CloudApiException(status_code=422, detail=error_msg) from e

    async with client_from_auth(auth) as aries_controller:
        sd_jws = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.wallet.sign_sd_jwt,
            body=sign_request,
        )

    result = SDJWSCreateResponse(sd_jws=sd_jws)
    bound_logger.debug("Successfully signed SD-JWS.")
    return result


@router.post(
    "/verify",
    summary="Verify SD-JWS",
)
async def verify_sd_jws(
    body: SDJWSVerifyRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> SDJWSVerifyResponse:
    """Verify a Selective Disclosure JSON Web Signature (SD-JWS).
    ---

    This endpoint allows users to verify the authenticity and integrity of a Selective Disclosure
    JSON Web Signature (SD-JWS). It decodes the SD-JWS to retrieve the payload and headers,
    assesses its validity, and processes the disclosures.

    **Usage:**

    - Submit the SD-JWS string concatenated with the necessary disclosures to this endpoint.
    - The format should be: `<Issuer-signed JWS>~<Disclosure 1>~<Disclosure 2>~...~<Disclosure N>`.
    - The holder provides the SD-JWS along with the required disclosures based on the verifier's request.

    **Notes:**

    - Only the disclosures relevant to the verifier's request needs to be provided.
      Other disclosures can remain confidential.

    **Example Request Body:**
    ```json
    {
        "sd_jws": "<Issuer-signed JWS>~<Disclosure 1>~<Disclosure 2>~...~<Disclosure N>"
    }
    ```

    Request Body:
    ---
        SDJWSVerifyRequest:
            `sd_jws` (str): The concatenated SD-JWS and disclosures to verify and reveal.

    Response:
    ---
        SDJWSVerifyResponse:
            `valid` (bool): Indicates whether the SD-JWS is valid.
            `payload` (dict): The decoded payload of the SD-JWS.
            `headers` (dict): The headers extracted from the SD-JWS.
            `kid` (str): The Key ID of the signer.
            `disclosed_attributes` (dict): The selectively disclosed attributes based on the provided disclosures.
            `error` (str, optional): Error message if the SD-JWS verification fails.

    **References:**

    - [Selective Disclosure JSON Web Token (SD-JWT)
      Specification](https://www.ietf.org/archive/id/draft-ietf-oauth-selective-disclosure-jwt-07.html)
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Verify SD-JWS")

    try:
        verify_request = SDJWSVerify(sd_jwt=body.sd_jws)
    except ValidationError as e:
        # Handle Pydantic validation error:
        error_msg = extract_validation_error_msg(e)
        error_msg = error_msg.replace("sd_jwt", "sd_jws")  # match the input field
        bound_logger.info(
            "Bad request: Validation error from SDJWSVerifyRequest body: {}", error_msg
        )
        raise CloudApiException(status_code=422, detail=error_msg) from e

    async with client_from_auth(auth) as aries_controller:
        verify_result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.wallet.verify_sd_jwt,
            body=verify_request,
        )

    result = SDJWSVerifyResponse(**verify_result.model_dump())
    bound_logger.debug("Successfully verified SD-JWS.")
    return result

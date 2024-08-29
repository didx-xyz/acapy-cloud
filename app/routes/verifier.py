from typing import List, Optional
from uuid import UUID

from aries_cloudcontroller import IndyCredPrecis
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException
from app.models.verifier import (
    AcceptProofRequest,
    CreateProofRequest,
    RejectProofRequest,
    SendProofRequest,
)
from app.util.acapy_verifier_utils import (
    VerifierFacade,
    assert_valid_prover,
    assert_valid_verifier,
    get_verifier_by_version,
)
from app.util.pagination import (
    descending_query_parameter,
    limit_query_parameter,
    offset_query_parameter,
    order_by_query_parameter,
)
from shared.log_config import get_logger
from shared.models.presentation_exchange import (
    PresentationExchange,
    Role,
    State,
    back_to_v1_presentation_state,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/verifier", tags=["verifier"])


@router.post(
    "/send-request",
    summary="Send a Proof Request to a connection",
    response_model=PresentationExchange,
)
async def send_proof_request(
    body: SendProofRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PresentationExchange:
    """
    Send proof request
    ---
    NB: Only a tenant with the verifier role can send a proof request.

    The verifier uses this endpoint to send a proof request to a specific connection, by providing the connection ID.

    The proof request type must be one of indy or ld_proof.
    ```json
        {
            "type": "indy" or "ld_proof",
            "indy_proof_request": {...}, <-- Required if type is "indy"
            "dif_proof_request": {...}, <-- Required if type is "ld_proof"
            "save_exchange_record": true <-- Whether the proof exchange record should be preserved after completion.
            "comment": "string", <-- This comment will appear in the proof record for the recipient as well
            "protocol_version": "v2", <-- "v1" is supported, but deprecated
            "connection_id": "string", <-- The verifier's reference to the connection to send this proof request to
        }
    ```
    For a detailed technical specification and informative diagrams
    related to the present proof process, refer to the [Aries Present Proof v2
    RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0454-present-proof-v2/README.md) and the [LD Proof
    Attachment RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0510-dif-pres-exch-attach/README.md).

    Request Body:
    ---
        body: SendProofRequest
            The proof request object

    Returns:
    ---
        PresentationExchange
            The presentation exchange record for this request
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Send proof request")

    try:
        verifier = get_verifier_by_version(body.protocol_version)

        async with client_from_auth(auth) as aries_controller:
            if body.connection_id:
                await assert_valid_verifier(
                    aries_controller=aries_controller, proof_request=body
                )

            bound_logger.debug("Sending proof request")
            result = await verifier.send_proof_request(
                controller=aries_controller, send_proof_request=body
            )
    except CloudApiException as e:
        bound_logger.info("Could not send proof request: {}", e)
        raise

    if result:
        bound_logger.debug("Successfully sent proof request.")
    else:
        bound_logger.warning("No result obtained from sending proof request.")
    return result


@router.post(
    "/create-request",
    summary="Create a Proof Request (not bound to a connection)",
    response_model=PresentationExchange,
)
async def create_proof_request(
    body: CreateProofRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PresentationExchange:
    """
    Creates a presentation request that is not bound to any specific proposal or connection
    ---
    This endpoint is used to create a proof request that is not bound to a connection. This means the proof request is
    not sent directly, but it will do the initial step of creating a proof exchange record,
    which the verifier can then use in the out of band (OOB) protocol.

    The OOB protocol allows proof requests to be sent over alternative channels, such as email or QR code, where a
    connection does not yet exist between holder and verifier.

    The proof request type must be one of indy or ld_proof.
    ```json
        {
            "type": "indy" or "ld_proof",
            "indy_proof_request": {...}, <-- Required if type is "indy"
            "dif_proof_request": {...}, <-- Required if type is "ld_proof"
            "save_exchange_record": true <-- Whether the proof exchange record should be preserved after completion.
            "comment": "string", <-- This comment will appear in the proof record for the recipient as well
            "protocol_version": "v2", <-- "v1" is supported, but deprecated
        }
    ```
    For a detailed technical specification and informative diagrams
    related to the present proof process, refer to the [Aries Present Proof v2
    RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0454-present-proof-v2/README.md) and the [LD Proof
    Attachment RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0510-dif-pres-exch-attach/README.md).

    Request Body:
    ---
        body: CreateProofRequest
            The proof request object

    Returns:
    ---
        PresentationExchange
            The presentation exchange record for this request
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Create proof request")

    try:
        verifier = get_verifier_by_version(body.protocol_version)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Creating proof request")
            result = await verifier.create_proof_request(
                controller=aries_controller, create_proof_request=body
            )
    except Exception as e:
        bound_logger.info("Could not create presentation record: {}.", e)
        raise

    if result:
        bound_logger.debug("Successfully created proof request.")
    else:
        bound_logger.warning("No result obtained from creating proof request.")
    return result


@router.post(
    "/accept-request",
    summary="Accept a Proof Request",
    response_model=PresentationExchange,
)
async def accept_proof_request(
    body: AcceptProofRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PresentationExchange:
    """
    Accept proof request
    ---
    A prover uses this endpoint to respond to a proof request, by sending a presentation to the verifier.

    An Indy presentation contains a mapping of the requested attributes to the wallet credential id of the prover.

    Example:
    ```json
    {
        "indy_presentation_spec": {
            "requested_attributes": {
                "surname": {
                    "cred_id": "10e6b03f-2b60-431a-9634-731594423120",
                    "revealed": true
                },
                "name": {
                    "cred_id": "10e6b03f-2b60-431a-9634-731594423120",
                    "revealed": true
                },
                "age": {
                    "cred_id": "10e6b03f-2b60-431a-9634-731594423120",
                    "revealed": true
                }
            }
        }
    }
    ```

    In the context of the holder's wallet, the `cred_id` is called the `referent`.

    The `revealed` parameter indicates whether the holder wants to reveal the attribute value to the verifier or not.

    Request Body:
    ---
        body: AcceptProofRequest
            The proof request object

    Returns:
    ---
        PresentationExchange
            The prover's updated presentation exchange record after responding to the proof request.
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Accept proof request")

    try:
        verifier = get_verifier_by_version(body.proof_id)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Get proof record")
            proof_record = await verifier.get_proof_record(
                controller=aries_controller, proof_id=body.proof_id
            )

            # If there is a connection id the proof is not connectionless
            if proof_record.connection_id:
                await assert_valid_prover(
                    aries_controller=aries_controller,
                    verifier=verifier,
                    presentation=body,
                )
            else:
                bound_logger.warning(
                    "No connection associated with proof. Skip validating prover"
                )

            bound_logger.debug("Accepting proof record")
            result = await verifier.accept_proof_request(
                controller=aries_controller, accept_proof_request=body
            )
    except CloudApiException as e:
        bound_logger.info("Could not accept proof request: {}", e)
        raise

    if result:
        bound_logger.debug("Successfully accepted proof request.")
    else:
        bound_logger.warning("No result obtained from accepting proof request.")
    return result


@router.post("/reject-request", summary="Reject a Proof Request", status_code=204)
async def reject_proof_request(
    body: RejectProofRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """
    Reject proof request
    ---
    A prover uses this endpoint to notify the verifier that they cannot or refuse to respond to a proof request.

    The prover provides the proof ID of the request that they want to reject, and a message (`problem_report`) that
    will display in the verifier's presentation exchange record as the rejection message.

    Request Body:
    ---
        body: RejectProofRequest
            proof_id: str
                The proof id of the presentation request that is being rejected
            problem_report: str
                A message to inform the verifier why their proof request is rejected
            delete_proof_record: bool (default: False)
                Can be set to true if the prover wishes to delete their record of the rejected presentation exchange.

    Returns:
    ---
        status_code: 204
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Reject proof request")

    try:
        verifier = get_verifier_by_version(body.proof_id)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Getting proof record")
            proof_record = await verifier.get_proof_record(
                controller=aries_controller, proof_id=body.proof_id
            )

            if proof_record.state != "request-received":
                message = (
                    "Proof record must be in state `request-received` to reject; "
                    f"record has state: `{proof_record.state}`."
                )
                bound_logger.info(message)
                raise CloudApiException(message, 400)

            bound_logger.debug("Rejecting proof request")
            await verifier.reject_proof_request(
                controller=aries_controller, reject_proof_request=body
            )
    except CloudApiException as e:
        bound_logger.info("Could not reject request: {}.", e)
        raise

    bound_logger.debug("Successfully rejected proof request.")


@router.get(
    "/proofs",
    summary="Get Presentation Exchange Records",
    response_model=List[PresentationExchange],
)
async def get_proof_records(
    limit: Optional[int] = limit_query_parameter,
    offset: Optional[int] = offset_query_parameter,
    order_by: Optional[str] = order_by_query_parameter,
    descending: bool = descending_query_parameter,
    connection_id: Optional[str] = None,
    role: Optional[Role] = None,
    state: Optional[State] = None,
    thread_id: Optional[UUID] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> List[PresentationExchange]:
    """
    Get all presentation exchange records for this tenant
    ---
    These records contains information about proof requests and presentations.

    The results can be filtered by connection_id, role, state, and thread_id.

    Parameters (Optional):
    ---
        limit: int: The maximum number of records to retrieve
        offset: int: The offset to start retrieving records from
        descending: bool - Whether to return results in descending order. Results are ordered by record created time.
        connection_id: str
        role: Role: "prover", "verifier"
        state: State: "presentation-received", "presentation-sent", "proposal-received", "proposal-sent",
                        "request-received", "request-sent", "abandoned", "done"
        thread_id: UUID

    Returns:
    ---
        List[PresentationExchange]
            The list of presentation exchange records

    """
    logger.debug("GET request received: Get all proof records")

    try:
        async with client_from_auth(auth) as aries_controller:
            logger.debug("Fetching v1 proof records")
            v1_records = await VerifierFacade.V1.value.get_proof_records(
                controller=aries_controller,
                limit=limit,
                offset=offset,
                order_by=order_by,
                descending=descending,
                connection_id=connection_id,
                role=role,
                state=back_to_v1_presentation_state(state) if state else None,
                thread_id=str(thread_id) if thread_id else None,
            )
            logger.debug("Fetching v2 proof records")
            v2_records = await VerifierFacade.V2.value.get_proof_records(
                controller=aries_controller,
                limit=limit,
                offset=offset,
                order_by=order_by,
                descending=descending,
                connection_id=connection_id,
                role=role,
                state=state,
                thread_id=str(thread_id) if thread_id else None,
            )
    except CloudApiException as e:
        logger.info("Could not fetch proof records: {}.", e)
        raise

    result = v1_records + v2_records  # TODO: V1 to be deprecated. No need to re-order
    if result:
        logger.debug("Successfully fetched v1 and v2 records.")
    else:
        logger.debug("No v1 or v2 records returned.")
    return result


@router.get(
    "/proofs/{proof_id}",
    summary="Get a Presentation Exchange Record",
    response_model=PresentationExchange,
)
async def get_proof_record(
    proof_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PresentationExchange:
    """
    Get a specific presentation exchange record
    ---
    This fetches a specific presentation exchange record by providing the proof ID.

    Parameters:
    ---
        proof_id: str
            The proof ID for the presentation request of interest

    Returns:
    ---
        PresentationExchange
            The presentation exchange record for the proof ID
    """
    bound_logger = logger.bind(body={"proof_id": proof_id})
    bound_logger.debug("GET request received: Get proof record by id")

    try:
        verifier = get_verifier_by_version(version_candidate=proof_id)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Fetching proof record")
            result = await verifier.get_proof_record(
                controller=aries_controller, proof_id=proof_id
            )
    except CloudApiException as e:
        logger.info("Could not fetch proof record: {}.", e)
        raise

    if result:
        bound_logger.debug("Successfully fetched proof record.")
    else:
        bound_logger.debug("No record returned.")
    return result


@router.delete(
    "/proofs/{proof_id}",
    summary="Delete a Presentation Exchange Record",
    status_code=204,
)
async def delete_proof(
    proof_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """
    Delete a presentation exchange record
    ---
    This will remove a specific presentation exchange from your storage records.

    Parameters:
    ---
        proof_id: str
            The identifier of the presentation exchange record that you want to delete

    Returns:
    ---
        status_code: 204
    """
    bound_logger = logger.bind(body={"proof_id": proof_id})
    bound_logger.debug("DELETE request received: Delete proof record by id")

    try:
        verifier = get_verifier_by_version(version_candidate=proof_id)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Deleting proof record")
            await verifier.delete_proof(controller=aries_controller, proof_id=proof_id)
    except CloudApiException as e:
        bound_logger.info("Could not delete proof record: {}.", e)
        raise

    bound_logger.debug("Successfully deleted proof record.")


@router.get(
    "/proofs/{proof_id}/credentials",
    summary="Get Matching Credentials for a Proof",
    response_model=List[IndyCredPrecis],
)
async def get_credentials_by_proof_id(
    proof_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> List[IndyCredPrecis]:
    """
    Get matching credentials for a presentation exchange
    ---
    This endpoint returns a list of possible credentials that the prover can use to respond to a given proof request.

    The `presentation_referents` field indicates which of the fields in the proof request that credential satisfies.

    Parameters:
    ---
        proof_id: str
            The relevant proof exchange ID for the prover

    Returns:
    ---
        List[IndyCredPrecis]
            A list of applicable Indy credentials
    """
    bound_logger = logger.bind(body={"proof_id": proof_id})
    bound_logger.debug("GET request received: Get credentials for a proof request")

    try:
        verifier = get_verifier_by_version(version_candidate=proof_id)

        async with client_from_auth(auth) as aries_controller:
            bound_logger.debug("Fetching credentials for request")
            result = await verifier.get_credentials_by_proof_id(
                controller=aries_controller, proof_id=proof_id
            )
    except CloudApiException as e:
        bound_logger.info("Could not get matching credentials: {}.", e)
        raise

    bound_logger.debug("Successfully fetched credentials for proof request.")
    return result

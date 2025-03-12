from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException
from app.models.issuer import CreateOffer, CredentialType, SendCredential
from app.services.acapy_ledger import schema_id_from_credential_definition_id
from app.services.acapy_wallet import assert_public_did
from app.services.issuer.acapy_issuer_v2 import IssuerV2
from app.services.trust_registry.util.issuer import assert_valid_issuer
from app.util.did import did_from_credential_definition_id, qualified_did_sov
from app.util.pagination import (
    descending_query_parameter,
    limit_query_parameter,
    offset_query_parameter,
    order_by_query_parameter,
)
from app.util.save_exchange_record import save_exchange_record_query
from app.util.tenants import get_wallet_type
from shared.log_config import get_logger
from shared.models.credential_exchange import CredentialExchange, Role, State

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/issuer/credentials", tags=["issuer"])


@router.post("", summary="Send Holder a Credential", response_model=CredentialExchange)
async def send_credential(
    credential: SendCredential,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialExchange:
    """
    Create and send a credential, automating the issuer-side flow
    ---
    NB: Only a tenant with the issuer role can send credentials.

    When creating a credential, the credential type must be one of `indy` or `ld_proof`.
    ```json
    {
        "type": "indy" or "ld_proof",
        "indy_credential_detail": {...}, <-- Required if type is indy
        "ld_credential_detail": {...}, <-- Required if type is ld_proof
        "save_exchange_record": true, <-- Whether the credential exchange record should be saved on completion.
        "connection_id": "string", <-- The issuer's reference to the connection they want to submit the credential to.
    }
    ```
    Setting the `save_exchange_record` field to True will save the exchange record after the credential is accepted.
    The default behaviour is to only save exchange records while they are in pending state.

    For a detailed technical specification of the credential issuing process, refer to the [Aries Issue Credential v2
    RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0453-issue-credential-v2/README.md).

    Request Body:
    ---
        credential: SendCredential
            The payload for sending a credential

    Returns:
    ---
        CredentialExchange
            A record of this credential exchange
    """
    bound_logger = logger.bind(
        body={
            # Do not log credential attributes:
            "connection_id": credential.connection_id,
            "credential_type": credential.type,
        }
    )
    bound_logger.debug("POST request received: Send credential")

    async with client_from_auth(auth) as aries_controller:
        # Assert the agent has a public did
        try:
            public_did = await assert_public_did(aries_controller)
        except CloudApiException as e:
            bound_logger.warning("Asserting agent has public DID failed: {}", e)
            raise CloudApiException(
                "Wallet making this request has no public DID. Only issuers with a public DID can make this request.",
                403,
            ) from e

        wallet_type = await get_wallet_type(aries_controller, bound_logger)
        if (
            credential.type == CredentialType.ANONCREDS
            and wallet_type != "askar-anoncreds"
        ):
            raise CloudApiException(
                "AnonCreds credentials can only be issued by an askar-anoncreds wallet",
                400,
            )
        if credential.type == CredentialType.INDY and wallet_type == "askar-anoncreds":
            raise CloudApiException(
                "Indy credentials can only be issued by an askar wallet", 400
            )

        schema_id = None
        if credential.type == CredentialType.INDY:
            # Retrieve the schema_id based on the credential definition id
            schema_id = await schema_id_from_credential_definition_id(
                aries_controller,
                credential.indy_credential_detail.credential_definition_id,
                wallet_type,
            )
        if credential.type == CredentialType.ANONCREDS:
            schema_id = await schema_id_from_credential_definition_id(
                aries_controller,
                credential.anoncreds_credential_detail.credential_definition_id,
                wallet_type,
            )
        # Make sure we are allowed to issue according to trust registry rules
        await assert_valid_issuer(public_did, schema_id)

        try:
            bound_logger.debug("Sending credential")
            result = await IssuerV2.send_credential(
                controller=aries_controller, credential=credential
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to send credential: {e.detail}", e.status_code
            ) from e

    bound_logger.debug("Successfully sent credential.")
    return result


@router.post(
    "/create-offer",
    summary="Create a Credential Offer (not bound to a connection)",
    response_model=CredentialExchange,
)
async def create_offer(
    credential: CreateOffer,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialExchange:
    """
    Create a credential offer, not bound to any connection
    ---
    NB: Only a tenant with the issuer role can create credential offers.

    This endpoint takes the same body as the send credential endpoint, but without a connection id. This
    means the credential will not be sent, but it will do the initial step of creating a credential exchange record,
    which the issuer can then use in the out of band (OOB) protocol.

    The OOB protocol allows credentials to be sent over alternative channels, such as email or QR code, where a
    connection does not yet exist between holder and issuer.

    The credential type must be one of indy or ld_proof.
    ```json
    {
        "type": "indy" or "ld_proof",
        "indy_credential_detail": {...}, <-- Required if type is indy
        "ld_credential_detail": {...}, <-- Required if type is ld_proof
        "save_exchange_record": true, <-- Whether the credential exchange record should be saved on completion.
    }
    ```
    For a detailed technical specification of the credential issuing process, refer to the [Aries Issue Credential v2
    RFC](https://github.com/hyperledger/aries-rfcs/blob/main/features/0453-issue-credential-v2/README.md).

    Request Body:
    ---
        credential: CreateOffer
            The payload for creating a credential offer

    Returns:
    ---
        CredentialExchange
            A record of this credential exchange
    """
    bound_logger = logger.bind(
        body={
            # Do not log credential attributes:
            "credential_type": credential.type,
        }
    )
    bound_logger.debug("POST request received: Create credential offer")

    async with client_from_auth(auth) as aries_controller:
        # Assert the agent has a public did
        try:
            public_did = await assert_public_did(aries_controller)
        except CloudApiException as e:
            bound_logger.warning("Asserting agent has public DID failed: {}", e)
            raise CloudApiException(
                "Wallet making this request has no public DID. Only issuers with a public DID can make this request.",
                403,
            ) from e

        wallet_type = await get_wallet_type(aries_controller, bound_logger)
        if (
            credential.type == CredentialType.ANONCREDS
            and wallet_type != "askar-anoncreds"
        ):
            raise CloudApiException(
                "AnonCreds credentials can only be issued by an askar-anoncreds wallet",
                400,
            )
        if credential.type == CredentialType.INDY and wallet_type == "askar-anoncreds":
            raise CloudApiException(
                "Indy credentials can only be issued by an askar wallet", 400
            )

        schema_id = None
        if credential.type == CredentialType.INDY:
            # Retrieve the schema_id based on the credential definition id
            schema_id = await schema_id_from_credential_definition_id(
                aries_controller,
                credential.indy_credential_detail.credential_definition_id,
                wallet_type,
            )

        if credential.type == CredentialType.ANONCREDS:
            schema_id = await schema_id_from_credential_definition_id(
                aries_controller,
                credential.anoncreds_credential_detail.credential_definition_id,
                wallet_type,
            )

        # Make sure we are allowed to issue according to trust registry rules
        await assert_valid_issuer(public_did, schema_id)

        bound_logger.debug("Creating offer")
        result = await IssuerV2.create_offer(
            controller=aries_controller,
            credential=credential,
        )

    bound_logger.debug("Successfully created credential offer.")
    return result


@router.post(
    "/{credential_exchange_id}/request",
    summary="Accept a Credential Offer",
    response_model=CredentialExchange,
)
async def request_credential(
    credential_exchange_id: str,
    save_exchange_record: Optional[bool] = save_exchange_record_query,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialExchange:
    """
    Sends a request to accept a credential offer
    ---
    The holder uses this endpoint to accept an offer from an issuer.

    In technical terms, when a holder has a credential exchange record with a state 'offer-received', then they can use
    this endpoint to accept that credential offer, and store the credential in their wallet.

    Parameters:
    ---
        credential_exchange_id: str
            The holder's reference to the credential exchange that they want to accept
        save_exchange_record: Optional[bool]
            Whether to override environment setting for saving credential exchange records. Default is None (use
            environment setting). True means save record, False means delete record.

    Returns:
    ---
        CredentialExchange
            An updated record of this credential exchange
    """
    bound_logger = logger.bind(body={"credential_exchange_id": credential_exchange_id})
    bound_logger.debug("POST request received: Send credential request")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching records")
        record = await IssuerV2.get_record(aries_controller, credential_exchange_id)

        schema_id = None
        if record.type in ["indy", "anoncreds"]:
            if not record.credential_definition_id or not record.schema_id:
                raise CloudApiException(
                    "Record has no credential definition or schema associated. "
                    "This probably means you haven't received an offer yet.",
                    412,
                )
            issuer_did = did_from_credential_definition_id(
                record.credential_definition_id
            )
            issuer_did = qualified_did_sov(issuer_did)
            schema_id = record.schema_id
        elif record.type == "ld_proof":
            issuer_did = record.did
        else:
            raise CloudApiException("Could not resolve record type")

        await assert_valid_issuer(issuer_did, schema_id)
        # Make sure the issuer is allowed to issue this credential according to trust registry rules

        auto_remove = None
        if isinstance(save_exchange_record, bool):
            auto_remove = not save_exchange_record

        bound_logger.debug("Requesting credential")
        result = await IssuerV2.request_credential(
            controller=aries_controller,
            credential_exchange_id=credential_exchange_id,
            auto_remove=auto_remove,
        )

    bound_logger.debug("Successfully sent credential request.")
    return result


@router.post(
    "/{credential_exchange_id}/store",
    summary="Store a Received Credential in Wallet",
    response_model=CredentialExchange,
    deprecated=True,
)
async def store_credential(
    credential_exchange_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialExchange:
    """
    NB: Deprecated because credentials are automatically stored in wallet after they are accepted
    ---

    Store a credential
    ---
    Store a credential by providing the credential exchange id.
    The credential exchange id is the id of the credential exchange record, not the credential itself.

    The holder only needs to call this endpoint if the holder receives a credential out of band

    The holder can store the credential in their wallet after receiving it from the issuer.

    Parameters:
    ---
        credential_exchange_id: str
            credential exchange record identifier

    Returns:
    ---
        CredentialExchange
            An updated record of this credential exchange
    """
    bound_logger = logger.bind(body={"credential_exchange_id": credential_exchange_id})
    bound_logger.debug("POST request received: Store credential")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Storing credential")
        result = await IssuerV2.store_credential(
            controller=aries_controller, credential_exchange_id=credential_exchange_id
        )

    bound_logger.debug("Successfully stored credential.")
    return result


@router.get(
    "",
    summary="Fetch Credential Exchange Records",
    response_model=List[CredentialExchange],
)
async def get_credentials(
    limit: Optional[int] = limit_query_parameter,
    offset: Optional[int] = offset_query_parameter,
    order_by: Optional[str] = order_by_query_parameter,
    descending: bool = descending_query_parameter,
    connection_id: Optional[str] = Query(None),
    role: Optional[Role] = Query(None),
    state: Optional[State] = Query(None),
    thread_id: Optional[UUID] = Query(None),
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> List[CredentialExchange]:
    """
    Get a list of credential exchange records
    ---
    Both holders and issuers can call this endpoint, because they each have their own records of a credential exchange.

    These records contain information about the credentials issued to a holder, such as the current state of the
    exchange, and other metadata such as the `connection_id` that a credential was submit to (if an issuer) or received
    from (if a holder). Each record in the list is related to a single credential exchange flow.

    NB: An issuer and a holder will have distinct credential exchange ids, despite referring to the same exchange.
    The `thread_id` is the only record attribute that will be the same for the holder and the issuer.

    An exchange record will automatically be deleted after a flow completes (i.e. when state is 'done'),
    unless the `save_exchange_record` was set to true.

    The following parameters can be set to filter the fetched exchange records: connection_id, role, state, thread_id.

    Parameters (Optional):
    ---
        limit: int - The maximum number of records to retrieve
        offset: int - The offset to start retrieving records from
        descending: bool - Whether to return results in descending order. Results are ordered by record created time.
        connection_id: str
        role: Role: "issuer", "holder"
        state: State: "proposal-sent", "proposal-received", "offer-sent", "offer-received",
                                 "request-sent", "request-received", "credential-issued", "credential-received",
                                 "credential-revoked", "abandoned", "done"
        thread_id: UUID

    Returns:
    ---
        List[CredentialExchange]
            A list of credential exchange records
    """
    bound_logger = logger.bind(body={"connection_id": connection_id})
    bound_logger.debug("GET request received: Get credentials")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching v2 records")
        result = await IssuerV2.get_records(
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

    if result:
        bound_logger.debug("Successfully fetched records.")
    else:
        bound_logger.debug("No records returned.")
    return result


@router.get(
    "/{credential_exchange_id}",
    summary="Fetch a single Credential Exchange Record",
    response_model=CredentialExchange,
)
async def get_credential(
    credential_exchange_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialExchange:
    """
    Get a credential exchange record by credential id
    ---
    Both holders and issuers can call this endpoint, because they each have their own records of a credential exchange.

    These records contain information about the credentials issued to a holder, such as the current state of the
    exchange, and other metadata such as the `connection_id` that a credential was submit to (if an issuer) or received
    from (if a holder).

    NB: An issuer and a holder will have distinct credential exchange ids, despite referring to the same exchange.
    The `thread_id` is the only record attribute that will be the same for the holder and the issuer.

    An exchange record will, by default, automatically be deleted after a flow completes (i.e. when state is 'done'),
    unless the `save_exchange_record` was set to true, or the wallet is configured to preserve records by default.

    The following parameters can be set to filter the fetched exchange records: connection_id, role, state, thread_id.

    Parameters:
    ---
        credential_exchange_id: str
            The identifier of the credential exchange record that you want to fetch

    Returns:
    ---
        CredentialExchange
            The credential exchange record
    """
    bound_logger = logger.bind(body={"credential_exchange_id": credential_exchange_id})
    bound_logger.debug("GET request received: Get credentials by credential id")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Getting credential record")
        result = await IssuerV2.get_record(
            controller=aries_controller, credential_exchange_id=credential_exchange_id
        )

    bound_logger.debug("Successfully fetched credential.")
    return result


@router.delete(
    "/{credential_exchange_id}", summary="Delete an Exchange Record", status_code=204
)
async def remove_credential_exchange_record(
    credential_exchange_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """
    Delete a credential exchange record
    ---
    This will remove a specific credential exchange from your storage records.

    Parameters:
    ---
        credential_exchange_id: str
            The identifier of the credential exchange record that you want to delete

    Returns:
    ---
        status_code: 204
    """
    bound_logger = logger.bind(body={"credential_exchange_id": credential_exchange_id})
    bound_logger.debug(
        "DELETE request received: Remove credential exchange record by id"
    )

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Deleting credential")
        await IssuerV2.delete_credential_exchange_record(
            controller=aries_controller, credential_exchange_id=credential_exchange_id
        )

    bound_logger.debug("Successfully deleted credential exchange record.")

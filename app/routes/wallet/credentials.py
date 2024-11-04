from typing import List, Optional

from aries_cloudcontroller import (
    AttributeMimeTypesResult,
    CredRevokedResult,
    W3CCredentialsListRequest,
)
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import handle_acapy_call
from app.models.wallet import CredInfoList, IndyCredInfo, VCRecord, VCRecordList
from app.util.pagination import limit_query_parameter, offset_query_parameter
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/wallet/credentials", tags=["wallet"])


@router.get(
    "",
    response_model=CredInfoList,
    summary="Fetch a list of credentials from the wallet",
)
async def list_credentials(
    limit: Optional[int] = limit_query_parameter,
    offset: Optional[int] = offset_query_parameter,
    wql: Optional[str] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredInfoList:
    """
    Fetch a list of credentials from the wallet
    ---

    The `wql` (Wallet Query Language) parameter can be used to filter credentials returned from the wallet.

    The following string will look for the credential with the attribute `age` with value `21`:

        {"attr::age::value": "21"}

    Optional Parameters:
    ---
        limit: int
            The number of records to return.
        offset: int
            The number of records to skip before starting to return records.
        wql: str
            A WQL query to filter records.

    Returns:
    ---
        CredInfoList
            A list of credential records.
    """
    logger.debug("GET request received: List credentials")

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching credentials")
        results = await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.credentials.get_records,
            count=str(limit),
            start=str(offset),
            wql=wql,
        )

    logger.debug("Successfully listed credentials.")
    return results


@router.get(
    "/{credential_id}",
    response_model=IndyCredInfo,
    summary="Fetch a credential by ID",
)
async def get_credential_record(
    credential_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> IndyCredInfo:
    """
    Fetch a specific credential by ID
    ---

    Parameters:
    ---
        credential_id: str
            The ID of the credential to fetch.

    Returns:
    ---
        IndyCredInfo
            The credential record.
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug("GET request received: Fetch specific credential by ID")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching credential")
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.get_record,
            credential_id=credential_id,
        )

    bound_logger.debug("Successfully fetched credential.")
    return result


@router.delete("/{credential_id}", status_code=204, summary="Delete a credential by ID")
async def delete_credential(
    credential_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """
    Remove a specific credential from the wallet by ID
    ---

    Parameters:
    ---
        credential_id: str
            The ID of the credential to delete.

    Returns:
    ---
        status_code: 204
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug("DELETE request received: Remove specific credential by ID")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Deleting credential")
        await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.delete_record,
            credential_id=credential_id,
        )

    bound_logger.debug("Successfully deleted credential.")


@router.get(
    "/{credential_id}/mime-types",
    response_model=AttributeMimeTypesResult,
    summary="Retrieve attribute MIME types of a credential",
)
async def get_credential_mime_types(
    credential_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> AttributeMimeTypesResult:
    """
    Retrieve attribute MIME types of a specific credential by ID
    ---

    Parameters:
    ---
        credential_id: str
            The ID of the credential to fetch attribute MIME types for.

    Returns:
    ---
        AttributeMimeTypesResult
            The attribute MIME types of the credential.
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug(
        "GET request received: Retrieve attribute MIME types for a specific credential"
    )

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching MIME types")
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.get_credential_mime_types,
            credential_id=credential_id,
        )

    bound_logger.debug("Successfully fetched attribute MIME types.")
    return result


@router.get(
    "/{credential_id}/revocation-status",
    response_model=CredRevokedResult,
    summary="Get revocation status of a credential",
)
async def get_credential_revocation_status(
    credential_id: str,
    from_: Optional[str] = None,
    to: Optional[str] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredRevokedResult:
    """
    Query the revocation status of a specific credential by ID
    ---

    The revocation status of a credential can be queried over a specific time range
    by passing unix timestamps to the `from_` and `to` parameters.
    Leaving these parameters blank will return the current revocation status.

    Parameters:
    ---
        credential_id: str
            The ID of the credential to query revocation status for.
        from_: Optional[str]
            The timestamp to start the query from.
        to: Optional[str]
            The timestamp to end the query at.

    Returns:
    ---
        CredRevokedResult
            The revocation status of the credential.
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug(
        "GET request received: Query revocation status for a specific credential"
    )

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching revocation status")
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.get_revocation_status,
            credential_id=credential_id,
            var_from=from_,
            to=to,
        )

    bound_logger.debug("Successfully fetched revocation status.")
    return result


@router.get(
    "/list/w3c",
    response_model=VCRecordList,
    summary="Fetch a list of W3C credentials from the wallet",
)
async def list_w3c_credentials(
    schema_ids: Optional[List[str]] = None,
    issuer_did: Optional[str] = None,
    limit: Optional[int] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> VCRecordList:
    """
    Fetch a list of W3C credentials from the wallet
    ---

    The W3C credentials can be filtered by the parameters provided.

    Optional Parameters:
    ---
        schema_ids: List[str]
            Schema identifiers to match
        issuer_did: str
            Credential issuer did to match
        limit: int
            Maximum number of results to return

    Returns:
    ---
        VCRecordList
            A list of W3C credential records.
    """
    logger.debug("GET request received: List W3C credentials")

    body = W3CCredentialsListRequest(
        schema_ids=schema_ids,
        issuer_id=issuer_did,
        max_results=limit,
    )

    async with client_from_auth(auth) as aries_controller:
        logger.debug("Fetching W3C credentials")
        results = await handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.credentials.get_w3c_credentials,
            body=body,
        )

    logger.debug("Successfully listed W3C credentials.")
    return results


@router.get(
    "/w3c/{credential_id}",
    response_model=VCRecord,
    summary="Fetch a W3C credential by ID",
)
async def get_w3c_credential(
    credential_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> VCRecord:
    """
    Fetch a specific W3C credential by ID
    ---

    Parameters:
    ---
        credential_id: str
            The ID of the W3C credential to fetch.

    Returns:
    ---
        VCRecord
            The W3C credential.
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug("GET request received: Fetch specific W3C credential by ID")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Fetching W3C credential")
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.get_w3c_credential,
            credential_id=credential_id,
        )

    bound_logger.debug("Successfully fetched W3C credential.")
    return result


@router.delete("/w3c/{credential_id}", status_code=204, summary="Delete W3C credential")
async def delete_w3c_credential(
    credential_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> None:
    """
    Remove a specific W3C credential from the wallet by ID
    ---

    Parameters:
    ---
        credential_id: str
            The ID of the W3C credential to delete.

    Returns:
    ---
        status_code: 204
    """
    bound_logger = logger.bind(credential_id=credential_id)
    bound_logger.debug("DELETE request received: Remove specific W3C credential by ID")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Deleting W3C credential")
        await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.delete_w3c_credential,
            credential_id=credential_id,
        )

    bound_logger.debug("Successfully deleted W3C credential.")

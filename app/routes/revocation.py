import asyncio
from typing import Optional

from aries_cloudcontroller import IssuerCredRevRecord, RevRegWalletUpdatedResult
from fastapi import APIRouter, Depends

from app.dependencies.acapy_clients import client_from_auth
from app.dependencies.auth import AcaPyAuth, acapy_auth_from_header
from app.exceptions import CloudApiException, handle_acapy_call
from app.models.issuer import (
    ClearPendingRevocationsRequest,
    ClearPendingRevocationsResult,
    PendingRevocations,
    PublishRevocationsRequest,
    RevokeCredential,
    RevokedResponse,
)
from app.services import revocation_registry
from app.util.retry_method import coroutine_with_retry_until_value
from app.util.tenants import get_wallet_type
from shared import PUBLISH_REVOCATIONS_TIMEOUT
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/issuer/credentials", tags=["revocation"])


@router.post("/revoke", summary="Revoke a Credential (if revocable)")
async def revoke_credential(
    body: RevokeCredential,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> RevokedResponse:
    """
    Revoke a credential
    ---
    Revoke a credential by providing the identifier of the exchange.

    If an issuer is going to revoke more than one credential, it is recommended to set the
    'auto_publish_on_ledger' field to False (default), and then batch publish the revocations using
    the 'publish-revocations' endpoint.

    By batching the revocations, the issuer can save on transaction fees related to
    publishing revocations to the ledger.

    Request Body:
    ---
        body: RevokeCredential
            - credential_exchange_id (str): The ID associated with the credential exchange that should be revoked.
            - auto_publish_on_ledger (bool): (True) publish revocation to ledger immediately, or
                (default, False) mark it pending

    Returns:
    ---
        RevokedResponse:
            revoked_cred_rev_ids:
              The revocation registry indexes that were revoked.
              Will be empty if the revocation was marked as pending.
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Revoke credential")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Revoking credential")
        result = await revocation_registry.revoke_credential(
            controller=aries_controller,
            credential_exchange_id=body.credential_exchange_id,
            auto_publish_to_ledger=body.auto_publish_on_ledger,
        )

    bound_logger.debug("Successfully revoked credential.")
    return result


@router.get(
    "/revocation/record",
    summary="Fetch a Revocation Record",
    response_model=IssuerCredRevRecord,
)
async def get_credential_revocation_record(
    credential_exchange_id: Optional[str] = None,
    credential_revocation_id: Optional[str] = None,
    revocation_registry_id: Optional[str] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> IssuerCredRevRecord:
    """
    Get a credential revocation record
    ---
    Fetch a credential revocation record by providing the credential exchange id.
    Records can also be fetched by providing the credential revocation id and revocation registry id.

    The record is the payload of the webhook event on topic 'issuer_cred_rev', and contains the credential's revocation
    status and other metadata.

    The revocation registry id (rev_reg_id) and credential revocation id (cred_rev_id) can be found
    in this record if you have the credential exchange id.

    Parameters:
    ---
        credential_exchange_id: str
        credential_revocation_id: str
        revocation_registry_id: str

    Returns:
    ---
        IssuerCredRevRecord
            The credential revocation record

    Raises:
    ---
        CloudApiException: 400
            If credential_exchange_id is not provided, both credential_revocation_id and revocation_registry_id must be.
    """
    bound_logger = logger.bind(
        body={
            "credential_exchange_id": credential_exchange_id,
            "credential_revocation_id": credential_revocation_id,
            "revocation_registry_id": revocation_registry_id,
        }
    )
    bound_logger.debug("GET request received: Get credential revocation record by id")

    if credential_exchange_id is None and (
        credential_revocation_id is None or revocation_registry_id is None
    ):
        raise CloudApiException(
            "If credential_exchange_id is not provided then both "
            "credential_revocation_id and revocation_registry_id must be provided.",
            400,
        )

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Getting credential revocation record")
        revocation_record = await revocation_registry.get_credential_revocation_record(
            controller=aries_controller,
            credential_exchange_id=credential_exchange_id,
            credential_revocation_id=credential_revocation_id,
            revocation_registry_id=revocation_registry_id,
        )

    bound_logger.debug("Successfully fetched credential revocation record.")
    return revocation_record


@router.post("/publish-revocations", summary="Publish Pending Revocations")
async def publish_revocations(
    publish_request: PublishRevocationsRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> RevokedResponse:
    """
    Write pending revocations to the ledger
    ---
    Revocations that are in a pending state can be published to the ledger.

    The endpoint accepts a `revocation_registry_credential_map`, which provides a dictionary of
    revocation registry IDs to credential revocation IDs, to allow publishing individual credentials.

    If no revocation registry id is provided (i.e. an empty map `revocation_registry_credential_map: {}`),
    then all pending revocations will be published.

    If no credential revocation id is provided under a given revocation registry id, then all pending revocations for
    the given revocation registry id will be published.

    Where to find the revocation registry id and credential revocation id:
    When issuing a credential, against a credential definition that supports revocation,
    the issuer will receive a webhook event on the topic 'issuer_cred_rev'. This event will contain
    the credential exchange id (cred_ex_id), the credential revocation id (cred_rev_id) and
    the revocation registry id (rev_reg_id).

    Request Body:
    ---
        publish_request: PublishRevocationsRequest
            An instance of `PublishRevocationsRequest` containing a `revocation_registry_credential_map`. This map
            is a dictionary where each key is a revocation registry ID and its value is a list of credential
            revocation IDs to be published. Providing an empty list for a registry ID instructs the system to
            publish all pending revocations for that ID. An empty dictionary signifies that all pending
            revocations across all registry IDs should be published.

    Returns:
    ---
        RevokedResponse:
            revoked_cred_rev_ids:
              The revocation registry indexes that were revoked.
              Will be empty if there were no revocations to publish.
    """
    bound_logger = logger.bind(body=publish_request)
    bound_logger.debug("POST request received: Publish revocations")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Publishing revocations")
        result = await revocation_registry.publish_pending_revocations(
            controller=aries_controller,
            revocation_registry_credential_map=publish_request.revocation_registry_credential_map,
        )

        if not result:
            bound_logger.debug("No revocations to publish.")
            return RevokedResponse()
        # TODO The anoncreds response seems to be broken, looks like agent response model not what it's
        # supposed to be. Need to investigate further.
        endorser_transaction_ids = [txn.transaction_id for txn in result.txn]
        for endorser_transaction_id in endorser_transaction_ids:
            bound_logger.debug(
                "Wait for publish complete on transaction id: {}",
                endorser_transaction_id,
            )
            try:
                # Wait for transaction to be acknowledged and written to the ledger
                await coroutine_with_retry_until_value(
                    coroutine_func=aries_controller.endorse_transaction.get_transaction,
                    args=(endorser_transaction_id,),
                    field_name="state",
                    expected_value="transaction_acked",
                    logger=bound_logger,
                    max_attempts=PUBLISH_REVOCATIONS_TIMEOUT,
                    retry_delay=1,
                )
            except asyncio.TimeoutError as e:
                raise CloudApiException(
                    "Timeout waiting for endorser to accept the revocations request.",
                    504,
                ) from e

    bound_logger.debug("Successfully published revocations.")
    return RevokedResponse.model_validate(result.model_dump())


@router.post(
    "/clear-pending-revocations",
    summary="Clear Pending Revocations",
    response_model=ClearPendingRevocationsResult,
)
async def clear_pending_revocations(
    clear_pending_request: ClearPendingRevocationsRequest,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> ClearPendingRevocationsResult:
    """
    Clear pending revocations
    ---
    Revocations that are in a pending state can be cleared, such that they are no longer set to be revoked.

    The endpoint accepts a `revocation_registry_credential_map`, which provides a dictionary of
    revocation registry IDs to credential revocation IDs, to allow clearing individual credentials.

    If no revocation registry id is provided (i.e. an empty map `revocation_registry_credential_map: {}`),
    then all pending revocations will be cleared.

    If no credential revocation id is provided under a given revocation registry id, then all pending revocations for
    the given revocation registry id will be cleared.

    Where to find the revocation registry id and credential revocation id:
    When issuing a credential, against a credential definition that supports revocation,
    the issuer will receive a webhook event on the topic 'issuer_cred_rev'. This event will contain
    the credential exchange id (cred_ex_id), the credential revocation id (cred_rev_id) and
    the revocation registry id (rev_reg_id).

    Request Body:
    ---
        clear_pending_request: ClearPendingRevocationsRequest
            An instance of `ClearPendingRevocationsRequest` containing a `revocation_registry_credential_map`. This map
            is a dictionary where each key is a revocation registry ID and its value is a list of credential
            revocation IDs to be cleared. Providing an empty list for a registry ID instructs the system to
            clear all pending revocations for that ID. An empty dictionary signifies that all pending
            revocations across all registry IDs should be cleared.

    Returns:
    ---
        ClearPendingRevocationsResult
            The revocations that are still pending after the clear request is performed
    """
    bound_logger = logger.bind(body=clear_pending_request)
    bound_logger.debug("POST request received: Clear pending revocations")

    async with client_from_auth(auth) as aries_controller:
        wallet_type = get_wallet_type(aries_controller, bound_logger)
        if wallet_type == "anoncreds":
            raise CloudApiException(
                "Clearing pending revocations is not supported for the 'anoncreds' wallet type.",
                500,
            )
        bound_logger.debug("Clearing pending revocations")
        response = await revocation_registry.clear_pending_revocations(
            controller=aries_controller,
            revocation_registry_credential_map=clear_pending_request.revocation_registry_credential_map,
        )

    bound_logger.debug("Successfully cleared pending revocations.")
    return response


@router.get(
    "/get-pending-revocations/{revocation_registry_id}",
    summary="Get Pending Revocations",
)
async def get_pending_revocations(
    revocation_registry_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> PendingRevocations:
    """
    Get pending revocations
    ---
    Get the pending revocations for a given revocation registry ID.

    Parameters:
    ---
        revocation_registry_id: str
            The ID of the revocation registry for which to fetch pending revocations

    Returns:
    ---
        PendingRevocations:
            A list of cred_rev_ids pending revocation for a given revocation registry ID
    """
    bound_logger = logger.bind(body={"revocation_registry_id": revocation_registry_id})
    bound_logger.debug("GET request received: Get pending revocations")

    async with client_from_auth(auth) as aries_controller:
        bound_logger.debug("Getting pending revocations")
        result = await revocation_registry.get_pending_revocations(
            controller=aries_controller, rev_reg_id=revocation_registry_id
        )

    bound_logger.debug("Successfully fetched pending revocations.")
    return PendingRevocations(pending_cred_rev_ids=result)


@router.put(
    "/fix-revocation-registry/{revocation_registry_id}",
    summary="Fix Revocation Registry Entry State",
)
async def fix_revocation_registry_entry_state(
    revocation_registry_id: str,
    apply_ledger_update: bool = False,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> RevRegWalletUpdatedResult:
    """
    Fix Revocation Registry Entry State
    ---
    Fix the revocation registry entry state for a given revocation registry ID.

    If issuer's revocation registry wallet state is out of sync with the ledger,
    this endpoint can be used to fix/update the ledger state.

    Path Parameters:
    ---
        revocation_registry_id: str
            The ID of the revocation registry for which to fix the state

    Query Parameters:
    ---
        apply_ledger_update: bool
            Apply changes to ledger (default: False). If False, only computes the difference
            between the wallet and ledger state.

    Returns:
    ---
        RevRegWalletUpdatedResult:
            accum_calculated: The calculated accumulator value for any revocations not yet published to ledger
            accum_fixed: The result of applying the ledger transaction to synchronize revocation state
            rev_reg_delta: The delta between wallet and ledger state for this revocation registry
    """
    bound_logger = logger.bind(
        body={
            "revocation_registry_id": revocation_registry_id,
            "apply_ledger_update": apply_ledger_update,
        }
    )
    bound_logger.debug("PUT request received: Fix revocation registry entry state")

    async with client_from_auth(auth) as aries_controller:
        wallet_type = get_wallet_type(aries_controller, bound_logger)
        if wallet_type == "anoncreds":
            bound_logger.debug("Fixing revocation registry entry state")
            response = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.anoncreds_revocation.update_rev_reg_revoked_state,
                rev_reg_id=revocation_registry_id,
                apply_ledger_update=apply_ledger_update,
            )

        elif wallet_type == "askar":
            bound_logger.debug("Fixing revocation registry entry state")
            response = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.revocation.update_rev_reg_revoked_state,
                rev_reg_id=revocation_registry_id,
                apply_ledger_update=apply_ledger_update,
            )

    bound_logger.debug("Successfully fixed revocation registry entry state.")
    return response

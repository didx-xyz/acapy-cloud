import asyncio
from typing import Dict, List, Literal, Optional

from aries_cloudcontroller import (
    AcaPyClient,
    ClearPendingRevocationsRequest,
    CredRevRecordResult,
    CredRevRecordResultSchemaAnonCreds,
    IssuerCredRevRecord,
    IssuerRevRegRecord,
    PublishRevocations,
    PublishRevocationsOptions,
    PublishRevocationsResultSchemaAnonCreds,
    PublishRevocationsSchemaAnonCreds,
    RevokeRequest,
    RevokeRequestSchemaAnonCreds,
    RevRegResult,
    TxnOrPublishRevocationsResult,
)

from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.issuer import ClearPendingRevocationsResult, RevokedResponse
from app.util.credentials import strip_protocol_prefix
from app.util.retry_method import coroutine_with_retry
from app.util.wallet_type_checks import get_wallet_type
from shared.log_config import get_logger

logger = get_logger(__name__)


async def get_active_revocation_registry_for_credential(
    controller: AcaPyClient, credential_definition_id: str
) -> IssuerRevRegRecord:
    """
        Get the active revocation registry for a credential

    Args:
        controller (AcaPyClient): aca-py client
        credential_definition_id (str): The credential definition ID.

    Raises:
        Exception: When the active revocation registry cannot be retrieved.

    Returns:
        result (IssuerRevRegRecord): The revocation registry record.
    """
    bound_logger = logger.bind(
        body={"credential_definition_id": credential_definition_id}
    )
    bound_logger.debug("Fetching activate revocation registry for a credential")

    result = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=controller.revocation.get_active_registry_for_cred_def,
        cred_def_id=credential_definition_id,
    )

    if not isinstance(result, RevRegResult):
        bound_logger.error(
            "Unexpected type returned from get_active_registry_for_cred_def: `{}`.",
            result,
        )
        raise CloudApiException(
            "Error retrieving revocation registry for credential with ID "
            f"`{credential_definition_id}`."
        )

    bound_logger.debug(
        "Successfully retrieved revocation registry for credential definition."
    )
    return result.result


async def revoke_credential(
    controller: AcaPyClient,
    credential_exchange_id: str,
    auto_publish_to_ledger: bool = False,
) -> RevokedResponse:
    """
        Revoke an issued credential

    Args:
        controller (AcaPyClient): aca-py client
        credential_exchange_id (str): The credential exchange ID.
        auto_publish_to_ledger (bool): (True) publish revocation to ledger immediately,
            or (default, False) mark it pending

    Raises:
        Exception: When the credential could not be revoked

    Returns:
        result (None): Successful execution returns None.
    """
    bound_logger = logger.bind(
        body={
            "credential_exchange_id": credential_exchange_id,
            "auto_publish_to_ledger": auto_publish_to_ledger,
        }
    )
    bound_logger.debug("Revoking an issued credential")
    wallet_type = await get_wallet_type(controller, bound_logger)

    if wallet_type == "askar-anoncreds":
        request_body = handle_model_with_validation(
            logger=bound_logger,
            model_class=RevokeRequestSchemaAnonCreds,
            cred_ex_id=strip_protocol_prefix(credential_exchange_id),
            publish=auto_publish_to_ledger,
        )

        acapy_call = controller.anoncreds_revocation.revoke

    else:  # wallet_type == "askar":
        request_body = handle_model_with_validation(
            logger=bound_logger,
            model_class=RevokeRequest,
            cred_ex_id=strip_protocol_prefix(credential_exchange_id),
            publish=auto_publish_to_ledger,
        )

        acapy_call = controller.revocation.revoke_credential

    try:
        revoke_result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=acapy_call,
            body=request_body,
        )
    except CloudApiException as e:
        raise CloudApiException(
            f"Failed to revoke credential: {e.detail}", e.status_code
        ) from e

    if auto_publish_to_ledger:
        bound_logger.debug("Wait for publish complete")

        revoked = False
        max_tries = 5
        retry_delay = 1
        n_try = 0
        while not revoked and n_try < max_tries:
            n_try += 1
            # Safely fetch revocation record and check if change reflected
            if wallet_type == "askar-anoncreds":
                coroutine_func = controller.anoncreds_revocation.get_cred_rev_record

            else:  # wallet_type == "askar":
                coroutine_func = controller.revocation.get_revocation_status

            record = await coroutine_with_retry(
                coroutine_func=coroutine_func,
                args=(strip_protocol_prefix(credential_exchange_id),),
                logger=bound_logger,
                max_attempts=5,
                retry_delay=0.5,
            )
            # Todo: this record state can be "revoked" before it's been endorsed
            if record.result:
                revoked = record.result.state == "revoked"

            if not revoked and n_try < max_tries:
                bound_logger.debug("Not yet revoked, waiting ...")
                await asyncio.sleep(retry_delay)

        if not revoked or not record.result:
            raise CloudApiException(
                "Could not assert that revocation was published within timeout. "
                "Please check the revocation record state and retry if not revoked."
            )

        if wallet_type == "askar-anoncreds":
            assert (
                record.result.rev_reg_id is not None
            ), "rev_reg_id is not present in the revocation response"
            assert (
                record.result.cred_rev_id is not None
            ), "cred_rev_id is not present in the revocation response"

            return RevokedResponse(
                cred_rev_ids_published={
                    record.result.rev_reg_id: [int(record.result.cred_rev_id)]
                }
            )

        if not revoke_result:
            raise CloudApiException(
                "Revocation was published but no result was returned. "
                "Has this credential been revoked before?"
            )

        if revoke_result.get("txn") and revoke_result["txn"].get("messages_attach"):
            bound_logger.debug("Successfully revoked credential.")
            return RevokedResponse.model_validate({"txn": [revoke_result["txn"]]})

    bound_logger.debug("Successfully revoked credential.")
    return RevokedResponse()


async def publish_pending_revocations(
    controller: AcaPyClient, revocation_registry_credential_map: Dict[str, List[str]]
) -> Optional[TxnOrPublishRevocationsResult]:
    """
        Publish pending revocations

    Args:
        controller (AcaPyClient): aca-py client
        revocation_registry_credential_map (Dict[str, List[str]]): A dictionary where each key is a
            revocation registry ID and its value is a list of credential revocation IDs to be cleared.

    Raises:
        Exception: When the pending revocations could not be published

    Returns:
        result (str): Successful execution returns the endorser transaction id.
    """
    bound_logger = logger.bind(body=revocation_registry_credential_map)

    await validate_rev_reg_ids(
        controller=controller,
        revocation_registry_credential_map=revocation_registry_credential_map,
    )
    wallet_type = await get_wallet_type(controller, bound_logger)
    try:
        if wallet_type == "askar-anoncreds":
            acapy_call = controller.anoncreds_revocation.publish_revocations
            body = PublishRevocationsSchemaAnonCreds(
                rrid2crid=revocation_registry_credential_map,
                options=PublishRevocationsOptions(
                    create_transaction_for_endorser=False
                ),
            )
        else:  # wallet_type == "askar":
            acapy_call = controller.revocation.publish_revocations
            body = PublishRevocations(rrid2crid=revocation_registry_credential_map)

        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=acapy_call,
            body=body,
        )
    except CloudApiException as e:
        raise CloudApiException(
            f"Failed to publish pending revocations: {e.detail}", e.status_code
        ) from e

    if isinstance(result, TxnOrPublishRevocationsResult):
        if not result.txn or not result.txn[0].transaction_id:
            bound_logger.warning(
                "Published pending revocations but received no endorser transaction id. Got result: {}",
                result,
            )
            return

        bound_logger.debug(
            "Successfully published pending Indy revocations. Endorser transaction ids: {}.",
            [txn.transaction_id for txn in result.txn],
        )
        return result
    elif isinstance(result, PublishRevocationsResultSchemaAnonCreds):
        bound_logger.info(
            "Successfully published pending AnonCreds revocations: {}.", result
        )
        # Cast integer cred_rev_ids to string
        rrid2crid = result.rrid2crid if result.rrid2crid else {}
        rrid2crid = {k: [str(i) for i in v] for k, v in result.rrid2crid.items()}
        return TxnOrPublishRevocationsResult(
            rrid2crid=rrid2crid,
            txn=None,
        )
    else:
        bound_logger.warning(
            "Unexpected response from publish_revocations: `{}`. Perhaps empty publish request?",
            result,
        )
        return


async def clear_pending_revocations(
    controller: AcaPyClient, revocation_registry_credential_map: Dict[str, List[str]]
) -> ClearPendingRevocationsResult:
    """
        Clear pending revocations

    Args:
        controller (AcaPyClient): aca-py client
        revocation_registry_credential_map (Dict[str, List[str]]): A dictionary where each key is a
            revocation registry ID and its value is a list of credential revocation IDs to be cleared.

    Raises:
        Exception: When the pending revocations could not be cleared

    Returns:
        ClearPendingRevocationsResult: The outstanding revocations after completing the clear request.
    """
    bound_logger = logger.bind(body=revocation_registry_credential_map)

    bound_logger.debug("Validating revocation registry ids")
    await validate_rev_reg_ids(
        controller=controller,
        revocation_registry_credential_map=revocation_registry_credential_map,
    )

    request_body = ClearPendingRevocationsRequest(
        purge=revocation_registry_credential_map
    )
    try:
        clear_result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.revocation.clear_pending_revocations,
            body=request_body,
        )
    except CloudApiException as e:
        raise CloudApiException(
            f"Failed to clear pending revocations: {e.detail}", e.status_code
        ) from e

    result = ClearPendingRevocationsResult(
        revocation_registry_credential_map=clear_result.rrid2crid
    )
    bound_logger.debug("Successfully cleared pending revocations.")
    return result


async def get_credential_revocation_record(
    controller: AcaPyClient,
    credential_exchange_id: Optional[str] = None,
    credential_revocation_id: Optional[str] = None,
    revocation_registry_id: Optional[str] = None,
) -> IssuerCredRevRecord:
    """
        Get the revocation status for a credential

    Args:
        controller (AcaPyClient): aca-py client
        credential_exchange_id (str): The credential exchange ID.
        credential_revocation_id (str): The credential revocation ID.
        revocation_registry_id (str): The revocation registry ID.

    Raises:
        Exception: When failed to get revocation status.

    Returns:
        IssuerCredRevRecord: The requested credential revocation record.
    """
    bound_logger = logger.bind(
        body={
            "credential_exchange_id": credential_exchange_id,
            "credential_revocation_id": credential_revocation_id,
            "revocation_registry_id": revocation_registry_id,
        }
    )
    bound_logger.debug("Fetching the revocation status for a credential exchange")
    wallet_type = await get_wallet_type(controller, bound_logger)
    try:
        if wallet_type == "askar-anoncreds":
            acapy_call = controller.anoncreds_revocation.get_cred_rev_record

        else:  # wallet_type == "askar":
            acapy_call = controller.revocation.get_revocation_status

        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=acapy_call,
            cred_ex_id=strip_protocol_prefix(credential_exchange_id),
            cred_rev_id=credential_revocation_id,
            rev_reg_id=revocation_registry_id,
        )
    except CloudApiException as e:
        raise CloudApiException(
            f"Failed to get revocation status: {e.detail}", e.status_code
        ) from e

    if not isinstance(
        result, (CredRevRecordResultSchemaAnonCreds, CredRevRecordResult)
    ):
        bound_logger.error(
            "Unexpected type returned from get_revocation_status: `{}`.", result
        )
        raise CloudApiException(
            "Error retrieving revocation status for credential exchange ID "
            f"`{credential_exchange_id}`."
        )

    result = result.result

    bound_logger.debug("Successfully retrieved revocation status.")
    return result


async def get_credential_definition_id_from_exchange_id(
    controller: AcaPyClient, credential_exchange_id: str
) -> Optional[str]:
    """
        Get the credential definition id from the credential exchange id.

    Args:
        controller (AcaPyClient): aca-py client
        credential_exchange_id (str): The credential exchange ID.

    Returns:
        credential_definition_id (Optional[str]): The credential definition ID or None.
    """
    bound_logger = logger.bind(body={"credential_exchange_id": credential_exchange_id})
    bound_logger.debug("Fetching credential definition id from exchange id")

    cred_ex_id = strip_protocol_prefix(credential_exchange_id)

    try:
        cred_ex_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.get_record,
            cred_ex_id=cred_ex_id,
        )
        rev_reg_id = cred_ex_record.indy.rev_reg_id
        rev_reg_parts = rev_reg_id.split(":")
        credential_definition_id = ":".join(
            [
                rev_reg_parts[2],
                "3",
                "CL",  # NOTE: update this with other signature types in future
                rev_reg_parts[-4],
                rev_reg_parts[-1],
            ]
        )
    except CloudApiException as err:
        bound_logger.info(
            "An Exception was caught while getting v2 record: '{}'",
            err.detail,
        )
        return
    except (KeyError, AttributeError):
        bound_logger.exception(
            "Exception caught while constructing cred def id from record."
        )
        return

    bound_logger.debug(
        "Successfully obtained cred definition id from the cred exchange id."
    )
    return credential_definition_id


async def validate_rev_reg_ids(
    controller: AcaPyClient, revocation_registry_credential_map: Dict[str, List[str]]
) -> None:
    """
        Validate revocation registry ids

    Args:
        controller (AcaPyClient): aca-py client
        revocation_registry_credential_map (Dict[str, List[str]]): A dictionary where each key is a
            revocation registry ID and its value is a list of credential revocation IDs to be cleared.

    Raises:
        Exception: When the revocation registry ids are invalid.

    """
    bound_logger = logger.bind(body=revocation_registry_credential_map)
    rev_reg_id_list = list(revocation_registry_credential_map.keys())

    if not rev_reg_id_list:
        return

    bound_logger.debug("Validating revocation registry ids")
    wallet_type = await get_wallet_type(controller, bound_logger)
    for rev_reg_id in rev_reg_id_list:
        try:
            if wallet_type == "askar-anoncreds":
                acapy_call = controller.anoncreds_revocation.get_revocation_registry

            else:  # wallet_type == "askar":
                acapy_call = controller.revocation.get_registry

            rev_reg_result = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=acapy_call,
                rev_reg_id=rev_reg_id,
            )

            if rev_reg_result.result is None:
                message = (
                    "Bad request: Failed to retrieve revocation registry "
                    f"'{rev_reg_id}'."
                )
                bound_logger.info(message)
                raise CloudApiException(message, status_code=404)

            pending_pub = rev_reg_result.result.pending_pub

            if pending_pub is None:
                message = (
                    "Bad request: No pending publications found for "
                    f"revocation registry '{rev_reg_id}'."
                )
                bound_logger.info(message)
                raise CloudApiException(message, status_code=404)

            bound_logger.debug(
                "Got the following pending publications for rev registry '{}': {}",
                rev_reg_id,
                pending_pub,
            )
            requested_cred_rev_ids = revocation_registry_credential_map[rev_reg_id]

            for cred_rev_id in requested_cred_rev_ids:
                if cred_rev_id not in pending_pub:
                    message = (
                        f"Bad request: the cred_rev_id: '{cred_rev_id}' "
                        f"is not pending publication for rev_reg_id: '{rev_reg_id}'."
                    )
                    bound_logger.info(message)
                    raise CloudApiException(message, 404)
        except CloudApiException as e:
            if e.status_code == 404:
                message = f"The rev_reg_id `{rev_reg_id}` does not exist: '{e.detail}'."
                bound_logger.info(message)
                raise CloudApiException(message, e.status_code) from e
            else:
                bound_logger.error(
                    "An Exception was caught while validating rev_reg_id: '{}'.",
                    e.detail,
                )
                raise CloudApiException(
                    (
                        "An error occurred while validating requested "
                        f"revocation registry credential map: '{e.detail}'."
                    ),
                    e.status_code,
                ) from e

    bound_logger.debug("Successfully validated revocation registry ids.")


async def get_created_active_registries(
    controller: AcaPyClient,
    cred_def_id: str,
    wallet_type: Literal["askar", "askar-anoncreds"],
) -> List[str]:
    """
    Get the active revocation registries for a credential definition with state active.

    """
    bound_logger = logger.bind(body={"cred_def_id": cred_def_id})
    try:
        if wallet_type == "askar-anoncreds":
            # Both will be in active state when created
            reg = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.anoncreds_revocation.get_revocation_registries,
                cred_def_id=cred_def_id,
                state="finished",
            )
        elif wallet_type == "askar":
            reg = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.revocation.get_created_registries,
                cred_def_id=cred_def_id,
                state="active",
            )
        return reg.rev_reg_ids
    except CloudApiException as e:
        detail = (
            "Error while creating credential definition: "
            + f"Could not retrieve active revocation registries `{e.detail}`."
        )
        raise CloudApiException(detail=detail, status_code=e.status_code) from e


async def wait_for_active_registry(
    controller: AcaPyClient,
    cred_def_id: str,
    wallet_type: Literal["askar", "askar-anoncreds"],
) -> List[str]:
    active_registries = []
    sleep_duration = 0  # First sleep should be 0

    # we want both active registries ready before trying to publish revocations to it
    while len(active_registries) < 2:
        await asyncio.sleep(sleep_duration)
        active_registries = await get_created_active_registries(
            controller, cred_def_id, wallet_type
        )
        sleep_duration = 0.5  # Following sleeps should wait 0.5s before retry

    return active_registries


async def get_pending_revocations(
    controller: AcaPyClient, rev_reg_id: str
) -> List[int]:
    """
    Get the pending revocations for a revocation registry.

    Args:
        controller (AcaPyClient): aca-py client
        rev_reg_id (str): The revocation registry ID.

    Raises:
        Exception: When the pending revocations could not be retrieved.

    Returns:
        pending_revocations (List[int]): The pending revocations.
    """
    bound_logger = logger.bind(body={"rev_reg_id": rev_reg_id})
    bound_logger.debug("Fetching pending revocations for a revocation registry")
    wallet_type = await get_wallet_type(controller, bound_logger)
    try:
        if wallet_type == "askar-anoncreds":
            acapy_call = controller.anoncreds_revocation.get_revocation_registry

        else:  # wallet_type == "askar":
            acapy_call = controller.revocation.get_registry

        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=acapy_call,
            rev_reg_id=rev_reg_id,
        )
    except CloudApiException as e:
        raise CloudApiException(
            f"Failed to get pending revocations: {e.detail}", e.status_code
        ) from e

    if not result.result:
        bound_logger.error("Unexpected type returned from get_registry: `{}`.", result)
        raise CloudApiException(
            f"Error retrieving pending revocations for revocation registry with ID `{rev_reg_id}`."
        )

    pending_revocations = result.result.pending_pub
    bound_logger.debug("Successfully retrieved pending revocations.")
    return pending_revocations

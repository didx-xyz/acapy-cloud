import asyncio
from logging import Logger
from typing import Literal

from aries_cloudcontroller import (
    DID,
    AcaPyClient,
    ConnRecord,
    InvitationCreateRequest,
    InvitationRecord,
)

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.wallet import DIDCreate
from app.services import acapy_ledger, acapy_wallet
from app.services.onboarding.util.set_endorser_metadata import (
    set_author_role,
    set_endorser_info,
    set_endorser_role,
)
from shared import ACAPY_ENDORSER_ALIAS, ISSUER_DID_ENDORSE_TIMEOUT


async def create_connection_with_endorser(
    *,
    endorser_controller: AcaPyClient,
    issuer_controller: AcaPyClient,
    endorser_did: DID,
    name: str,
    logger: Logger,
) -> str:
    invitation = await create_endorser_invitation(
        endorser_controller=endorser_controller, name=name, logger=logger
    )
    endorser_connection_id, issuer_connection_id = await wait_for_connection_completion(
        issuer_controller=issuer_controller,
        endorser_controller=endorser_controller,
        invitation=invitation,
        logger=logger,
    )
    await set_endorser_roles(
        endorser_controller=endorser_controller,
        issuer_controller=issuer_controller,
        endorser_connection_id=endorser_connection_id,
        issuer_connection_id=issuer_connection_id,
        logger=logger,
    )
    await configure_endorsement(
        issuer_controller=issuer_controller,
        issuer_connection_id=issuer_connection_id,
        endorser_did=endorser_did.did,
        logger=logger,
    )

    return issuer_connection_id


# todo: Migrate to endorser service
async def create_endorser_invitation(
    *, endorser_controller: AcaPyClient, name: str, logger: Logger
) -> InvitationRecord:
    logger.debug("Create OOB invitation on behalf of endorser")
    request_body = InvitationCreateRequest(
        alias=name,
        handshake_protocols=["https://didcomm.org/didexchange/1.1"],
        use_public_did=True,
    )
    invitation = await handle_acapy_call(
        logger=logger,
        acapy_call=endorser_controller.out_of_band.create_invitation,
        auto_accept=True,
        body=request_body,
    )
    logger.debug("Created OOB invitation")
    return invitation


async def wait_for_connection_completion(
    *,
    issuer_controller: AcaPyClient,
    endorser_controller: AcaPyClient,
    invitation: InvitationRecord,
    logger: Logger,
) -> tuple[str, str]:
    logger.debug("Receive invitation from endorser on behalf of issuer")
    issuer_connection_record = await handle_acapy_call(
        logger=logger,
        acapy_call=issuer_controller.out_of_band.receive_invitation,
        auto_accept=True,
        use_existing_connection=False,
        body=invitation.invitation,
        alias=ACAPY_ENDORSER_ALIAS,
    )

    invitation_msg_id = invitation.invi_msg_id
    try:
        endorser_connection = await wait_endorser_connection_completed(
            endorser_controller=endorser_controller,
            invitation_msg_id=invitation_msg_id,
            logger=logger,
        )
    except asyncio.TimeoutError as e:
        logger.error("Waiting for invitation complete event has timed out.")
        raise CloudApiException(
            "Timeout occurred while waiting for connection with endorser to complete.",
            504,
        ) from e

    logger.info("Connection complete between issuer and endorser.")

    endorser_connection_id = endorser_connection.connection_id
    issuer_connection_id = issuer_connection_record.connection_id

    return endorser_connection_id, issuer_connection_id


async def set_endorser_roles(
    *,
    endorser_controller: AcaPyClient,
    issuer_controller: AcaPyClient,
    endorser_connection_id: str,
    issuer_connection_id: str,
    logger: Logger,
) -> None:
    logger.debug("Setting roles for endorser")
    await set_endorser_role(
        endorser_controller=endorser_controller,
        endorser_connection_id=endorser_connection_id,
        logger=logger,
    )

    logger.debug("Setting roles for author")
    await set_author_role(
        issuer_controller=issuer_controller,
        issuer_connection_id=issuer_connection_id,
        logger=logger,
    )

    logger.debug("Successfully set roles for connection.")


async def configure_endorsement(
    *,
    issuer_controller: AcaPyClient,
    issuer_connection_id: str,
    endorser_did: str,
    logger: Logger,
) -> None:
    # Make sure endorsement has been configured
    # There is currently no way to retrieve endorser info. We'll just set it
    # to make sure the endorser info is set.
    logger.debug("Setting endorser info")
    await set_endorser_info(
        issuer_controller=issuer_controller,
        issuer_connection_id=issuer_connection_id,
        endorser_did=endorser_did,
        logger=logger,
    )
    logger.debug("Successfully set endorser info.")


async def register_issuer_did(
    *,
    issuer_controller: AcaPyClient,
    issuer_label: str,
    issuer_endorser_connection_id: str,
    did_method: Literal["sov", "cheqd"] = "sov",
    logger: Logger,
) -> DID:
    logger.info("Creating {} DID for issuer", did_method)
    issuer_did = await acapy_wallet.create_did(
        issuer_controller, did_create=DIDCreate(method=did_method)
    )

    if did_method == "sov":
        logger.debug("Accepting TAA on behalf of issuer")
        await acapy_ledger.accept_taa_if_required(issuer_controller)

        await acapy_ledger.register_nym_on_ledger(
            issuer_controller,
            did=issuer_did.did,
            verkey=issuer_did.verkey,
            alias=issuer_label,
            create_transaction_for_endorser=True,
        )

        logger.debug("Waiting for issuer DID transaction to be endorsed")
        await wait_transactions_endorsed(  # Needs to be endorsed before setting public DID
            issuer_controller=issuer_controller,
            issuer_connection_id=issuer_endorser_connection_id,
            logger=logger,
        )

        logger.debug("Setting public DID for issuer")
        await acapy_wallet.set_public_did(
            issuer_controller,
            did=issuer_did.did,
            create_transaction_for_endorser=True,
        )

        logger.debug("Waiting for ATTRIB transaction to be endorsed")
        await wait_transactions_endorsed(  # Needs to be endorsed before continuing
            issuer_controller=issuer_controller,
            issuer_connection_id=issuer_endorser_connection_id,
            logger=logger,
        )

    logger.debug("Issuer DID registered.")
    return issuer_did


async def wait_endorser_connection_completed(
    *,
    endorser_controller: AcaPyClient,
    invitation_msg_id: str,
    logger: Logger,
    max_attempts: int = 30,
    retry_delay: float = 0.5,
) -> ConnRecord:
    attempt = 0

    while attempt < max_attempts:
        try:
            invitation_connections = (
                await endorser_controller.connection.get_connections(
                    invitation_msg_id=invitation_msg_id
                )
            )

            for conn_record in invitation_connections.results:
                if conn_record.rfc23_state == "completed":
                    return conn_record

        except Exception as e:  # pylint: disable=W0718
            if attempt + 1 == max_attempts:
                logger.error(
                    "Maximum number of retries exceeded with exception. Failing."
                )
                raise asyncio.TimeoutError from e  # Raise TimeoutError if max attempts exceeded

            logger.warning(
                (
                    "Exception encountered (attempt {}). "
                    "Reason: \n{}.\n"
                    "Retrying in {} seconds..."
                ),
                attempt + 1,
                e,
                retry_delay,
            )

        await asyncio.sleep(retry_delay)
        attempt += 1

    logger.error("Maximum number of retries exceeded without returning expected value.")
    raise asyncio.TimeoutError


async def wait_transactions_endorsed(
    *,
    issuer_controller: AcaPyClient,
    issuer_connection_id: str,
    logger: Logger,
    max_attempts: int = ISSUER_DID_ENDORSE_TIMEOUT,
    retry_delay: float = 1.0,
) -> None:
    attempt = 0

    while attempt < max_attempts:
        try:
            transactions_response = (
                await issuer_controller.endorse_transaction.get_records()
            )

            transactions = [
                transaction
                for transaction in transactions_response.results
                if transaction.connection_id == issuer_connection_id
            ]

            if not transactions:
                logger.error(
                    "No transactions found for connection {}. Found {} transactions.",
                    issuer_connection_id,
                    transactions_response,
                )
                raise CloudApiException("No transactions found for connection", 404)

            all_acked = all(
                transaction.state == "transaction_acked" for transaction in transactions
            )

            if all_acked:
                return
            else:
                logger.debug(
                    "Waiting for transaction acknowledgements. Current states: {}",
                    ", ".join(f"{t.transaction_id}: {t.state}" for t in transactions),
                )

        except Exception as e:  # pylint: disable=W0718
            if attempt + 1 == max_attempts:
                logger.error(
                    "Maximum number of retries exceeded with exception. Failing."
                )
                raise asyncio.TimeoutError("Timeout waiting for endorsement") from e

            logger.warning(
                (
                    "Exception encountered (attempt {}). "
                    "Reason: \n{}.\n"
                    "Retrying in {} seconds..."
                ),
                attempt + 1,
                e,
                retry_delay,
            )

        await asyncio.sleep(retry_delay)
        attempt += 1

    logger.error("Maximum number of retries exceeded while waiting for transaction ack")
    raise asyncio.TimeoutError("Timeout waiting for endorsement")

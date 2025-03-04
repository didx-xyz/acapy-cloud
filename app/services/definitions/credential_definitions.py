import asyncio
from typing import List, Optional

from aries_cloudcontroller import (
    AcaPyClient,
    CredDefPostOptions,
    CredDefPostRequest,
    InnerCredDef,
)

from app.exceptions import handle_acapy_call, handle_model_with_validation
from app.models.definitions import CreateCredentialDefinition, CredentialDefinition
from app.services.definitions.credential_definition_publisher import (
    CredentialDefinitionPublisher,
)
from app.services.trust_registry.util.issuer import assert_valid_issuer
from app.util.assert_public_did import assert_public_did
from app.util.definitions import credential_definition_from_acapy
from app.util.transaction_acked import wait_for_transaction_ack
from shared import CRED_DEF_ACK_TIMEOUT, REGISTRY_SIZE
from shared.log_config import get_logger

logger = get_logger(__name__)


async def create_credential_definition(
    aries_controller: AcaPyClient,
    credential_definition: CreateCredentialDefinition,
    support_revocation: bool,
) -> str:
    """
    Create a credential definition
    """
    bound_logger = logger.bind(
        body={
            "schema_id": credential_definition.schema_id,
            "tag": credential_definition.tag,
            "support_revocation": credential_definition.support_revocation,
        }
    )
    publisher = CredentialDefinitionPublisher(
        controller=aries_controller, logger=bound_logger
    )

    public_did = await assert_public_did(aries_controller)

    await assert_valid_issuer(public_did, credential_definition.schema_id)

    if support_revocation:
        await publisher.check_endorser_connection()

    inner_cred_def = handle_model_with_validation(
        logger=logger,
        model_class=InnerCredDef,
        issuer_id=public_did[8:],
        schema_id=credential_definition.schema_id,
        tag=credential_definition.tag,
    )

    options = handle_model_with_validation(
        logger=logger,
        model_class=CredDefPostOptions,
        create_transaction_for_endorser=True,
        revocation_registry_size=REGISTRY_SIZE,
        support_revocation=support_revocation,
    )
    
    request_body = handle_model_with_validation(
        logger=logger,
        model_class=CredDefPostRequest,
        credential_definition=inner_cred_def,
        options=options,
    )

    result = await publisher.publish_credential_definition(request_body)
    credential_definition_id = (
        result.credential_definition_state.credential_definition_id
    )

    if result.registration_metadata["txn"]:
        await wait_for_transaction_ack(
            aries_controller=aries_controller,
            transaction_id=result.registration_metadata["txn"]["transaction_id"],
            max_attempts=CRED_DEF_ACK_TIMEOUT,
            retry_delay=1,
        )

    if support_revocation:
        await publisher.wait_for_revocation_registry(credential_definition_id)

    return credential_definition_id


async def get_credential_definitions(
    aries_controller: AcaPyClient,
    issuer_did: Optional[str] = None,
    credential_definition_id: Optional[str] = None,
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
) -> List[CredentialDefinition]:
    """
    Get credential definitions
    """
    bound_logger = logger.bind(
        body={
            "issuer_did": issuer_did,
            "credential_definition_id": credential_definition_id,
            "schema_id": schema_id,
            "schema_issuer_did": schema_issuer_did,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }
    )
    bound_logger.debug("Getting created credential definitions")

    response = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=aries_controller.anoncreds_credential_definitions.get_credential_definitions,
        issuer_did=issuer_did,
        schema_id=schema_id,
        schema_issuer_did=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )

    # Initiate retrieving all credential definitions
    credential_definition_ids = response.credential_definition_ids or []
    get_credential_definition_futures = [
        handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.anoncreds_credential_definitions.get_credential_definition,
            cred_def_id=credential_definition_id,
        )
        for credential_definition_id in credential_definition_ids
    ]

    # Wait for completion of retrieval and transform all credential definitions
    # into response model (if a credential definition was returned)
    if get_credential_definition_futures:
        bound_logger.debug("Getting definitions from fetched credential ids")
        credential_definition_results = await asyncio.gather(
            *get_credential_definition_futures
        )
    else:
        bound_logger.debug("No definition ids returned")
        credential_definition_results = []

    credential_definitions = [
        credential_definition_from_acapy(credential_definition.credential_definition)
        for credential_definition in credential_definition_results
        if credential_definition.credential_definition
    ]

    return credential_definitions

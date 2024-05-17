from enum import Enum
from typing import List, Optional, Set, Union

from aries_cloudcontroller import AcaPyClient, IndyPresSpec

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.verifier import AcceptProofRequest, ProofRequestType, SendProofRequest
from app.services.acapy_wallet import assert_public_did
from app.services.trust_registry.actors import fetch_actor_by_did, fetch_actor_by_name
from app.services.trust_registry.schemas import fetch_schemas
from app.services.verifier.acapy_verifier import Verifier
from app.services.verifier.acapy_verifier_v1 import VerifierV1
from app.services.verifier.acapy_verifier_v2 import VerifierV2
from app.util.did import ed25519_verkey_to_did_key, qualified_did_sov
from app.util.tenants import get_wallet_label_from_controller
from shared.exceptions import CloudApiValueError
from shared.log_config import get_logger
from shared.models.protocol import PresentProofProtocolVersion
from shared.models.trustregistry import Actor

logger = get_logger(__name__)


class VerifierFacade(Enum):
    v1 = VerifierV1
    v2 = VerifierV2


def get_verifier_by_version(
    version_candidate: Union[str, PresentProofProtocolVersion]
) -> Verifier:
    if version_candidate == PresentProofProtocolVersion.v1 or (
        isinstance(version_candidate, str) and version_candidate.startswith("v1-")
    ):
        return VerifierFacade.v1.value
    elif version_candidate == PresentProofProtocolVersion.v2 or (
        isinstance(version_candidate, str) and version_candidate.startswith("v2-")
    ):
        return VerifierFacade.v2.value
    else:
        raise CloudApiValueError(
            f"Unknown protocol version: `{version_candidate}`. Expecting `v1` or `v2`."
        )


async def assert_valid_prover(
    aries_controller: AcaPyClient, presentation: AcceptProofRequest, verifier: Verifier
) -> None:
    """Check transaction requirements against trust registry for prover"""
    # get connection record
    bound_logger = logger.bind(body=presentation)
    bound_logger.debug("Asserting valid prover")

    proof_id = presentation.proof_id

    bound_logger.debug("Getting connection from proof")
    connection_id = await get_connection_from_proof(
        aries_controller=aries_controller, proof_id=proof_id, verifier=verifier
    )

    if not connection_id:
        raise CloudApiException(
            "No connection id associated with proof request. Can not verify proof request.",
            400,
        )

    bound_logger.debug("Getting connection record")
    connection_record = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=aries_controller.connection.get_connection,
        conn_id=connection_id,
    )

    if not connection_record.connection_id:
        raise CloudApiException("Cannot proceed. No connection id.", 404)

    # Case 1: connection made with public DID
    if connection_record.their_public_did:
        public_did = qualified_did_sov(connection_record.their_public_did)
    # Case 2: connection made without public DID
    elif connection_record.invitation_key:
        invitation_key = connection_record.invitation_key
        public_did = ed25519_verkey_to_did_key(key=invitation_key)
    else:
        raise CloudApiException("Could not determine did of the verifier.", 400)

    # Try get actor from TR
    try:
        bound_logger.debug("Getting actor by DID")
        actor = await get_actor(did=public_did)
    except CloudApiException as e:
        their_label = connection_record.their_label
        if e.status_code == 404 and their_label:
            logger.info(
                "Actor did not found. Try fetch using `their_label` from connection: {}",
                their_label,
            )
            # DID is not found on Trust Registry. May arise if verifier has public did
            # (eg. has issuer role), but connection is made without using public did,
            # and their did:key is not on TR. Try fetch with label instead
            actor = await get_actor_by_name(name=their_label)
        elif e.status_code == 500:
            raise CloudApiException(
                "An error occurred while asserting valid verifier. Please try again.",
                500,
            ) from e
        else:
            logger.warning(
                "An unexpected exception occurred while asserting valid verifier: {}", e
            )
            raise

    # 2. Check actor has role verifier
    if not is_verifier(actor=actor):
        raise CloudApiException("Actor is missing required role 'verifier'.", 403)

    if presentation.type == ProofRequestType.INDY:
        # Get schema ids
        bound_logger.debug("Getting schema ids from presentation for Indy presentation")
        schema_ids = await get_schema_ids(
            aries_controller=aries_controller,
            presentation=presentation.indy_presentation_spec,
        )

        if not schema_ids:
            bound_logger.warning("No schema_ids associated with proof request.")

        # Verify the schemas are actually in the list from TR
        if not await are_valid_schemas(schema_ids=schema_ids):
            raise CloudApiException(
                "Presentation is using schemas not registered in trust registry.", 403
            )
    bound_logger.debug("Prover is valid.")


async def assert_valid_verifier(
    aries_controller: AcaPyClient,
    proof_request: SendProofRequest,
):
    """Check transaction requirements against trust registry for verifier"""

    # 1. Check agent has public did
    # CASE: Agent has public DID
    bound_logger = logger.bind(body=proof_request)
    bound_logger.debug("Asserting valid verifier")

    try:
        bound_logger.debug("Asserting public did")
        public_did = await assert_public_did(aries_controller=aries_controller)
    except Exception:
        # CASE: Agent has NO public DID
        # check via connection -> invitation key
        bound_logger.debug(
            "Agent has no public DID. Getting connection record from proof request"
        )
        connection_record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.connection.get_connection,
            conn_id=proof_request.connection_id,
        )

        # get invitation key
        invitation_key = connection_record.invitation_key

        if not invitation_key:
            raise CloudApiException("Connection has no invitation key.", 400)
        public_did = ed25519_verkey_to_did_key(invitation_key)

    # Try get actor from TR
    try:
        bound_logger.debug("Getting actor by DID")
        actor = await get_actor(did=public_did)
    except CloudApiException as e:
        if e.status_code == 404:
            # DID is not found on Trust Registry. May arise if verifier has no public did, and
            # connection is made without using OOB invite from Trust Registry
            try:
                wallet_label = await get_wallet_label_from_controller(aries_controller)
            except (IndexError, KeyError):
                logger.error("Could not read wallet_label from client's controller")
                raise e
            actor = await get_actor_by_name(name=wallet_label)
        elif e.status_code == 500:
            raise CloudApiException(
                "An error occurred while asserting valid verifier. Please try again.",
                500,
            ) from e
        else:
            logger.warning(
                "An unexpected exception occurred while asserting valid verifier: {}", e
            )
            raise

    # 2. Check actor has role verifier, raise exception otherwise
    if not is_verifier(actor=actor):
        raise CloudApiException(
            f"{actor.name} is not a valid verifier in the trust registry.", 403
        )
    bound_logger.debug("Verifier is valid.")


async def are_valid_schemas(schema_ids: List[str]) -> bool:
    if not schema_ids:
        return False

    schemas_from_tr = await fetch_schemas()
    schemas_ids_from_tr = [schema.id for schema in schemas_from_tr]
    schemas_valid_list = [id in schemas_ids_from_tr for id in schema_ids]

    return all(schemas_valid_list)


def is_verifier(actor: Actor) -> bool:
    return "verifier" in actor.roles


async def get_actor(did: str) -> Actor:
    actor = await fetch_actor_by_did(did)
    # Verify actor was in TR
    if not actor:
        raise CloudApiException(f"No verifier with DID `{did}`.", 404)
    return actor


async def get_actor_by_name(name: str) -> Actor:
    actor = await fetch_actor_by_name(name)
    # Verify actor was in TR
    if not actor:
        raise CloudApiException(f"No verifier with name `{name}`.", 404)
    return actor


async def get_schema_ids(
    aries_controller: AcaPyClient, presentation: IndyPresSpec
) -> List[str]:
    """Get schema ids from credentials that will be revealed in the presentation"""
    bound_logger = logger.bind(body=presentation)
    bound_logger.debug("Get schema ids from presentation")
    revealed_schema_ids: Set[str] = set()

    revealed_attr_cred_ids = [
        attr.cred_id
        for _, attr in presentation.requested_attributes.items()
        if attr.revealed
    ]
    revealed_predicate_cred_ids = [
        predicate.cred_id for _, predicate in presentation.requested_predicates.items()
    ]

    revealed_cred_ids = set([*revealed_attr_cred_ids, *revealed_predicate_cred_ids])

    logger.bind(body=revealed_cred_ids).debug(
        "Getting records from each of the revealed credential ids"
    )
    for revealed_cred_id in revealed_cred_ids:
        credential = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=aries_controller.credentials.get_record,
            credential_id=revealed_cred_id,
        )

        if credential.schema_id:
            revealed_schema_ids.add(credential.schema_id)

    result = list(revealed_schema_ids)
    if result:
        bound_logger.debug("Successfully got schema ids from presentation.")
    else:
        bound_logger.debug("No schema ids obtained from presentation.")
    return result


async def get_connection_from_proof(
    aries_controller: AcaPyClient, verifier: Verifier, proof_id: str
) -> Optional[str]:
    proof_record = await verifier.get_proof_record(
        controller=aries_controller, proof_id=proof_id
    )
    return proof_record.connection_id

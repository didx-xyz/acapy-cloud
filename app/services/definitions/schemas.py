import asyncio
from typing import List, Optional

from aries_cloudcontroller import AcaPyClient, SchemaGetResult, SchemaSendRequest

from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.definitions import CreateSchema, CredentialSchema
from app.routes.trust_registry import (
    get_schema_by_id as get_trust_registry_schema_by_id,
)
from app.routes.trust_registry import get_schemas as get_trust_registry_schemas
from app.services.definitions.schema_publisher import SchemaPublisher
from app.util.definitions import credential_schema_from_acapy
from shared.constants import GOVERNANCE_AGENT_URL
from shared.log_config import get_logger

logger = get_logger(__name__)


async def create_schema(
    aries_controller: AcaPyClient,
    schema: CreateSchema,
) -> CredentialSchema:
    """
    Create a schema and register it in the trust registry
    """
    bound_logger = logger.bind(body=schema)
    publisher = SchemaPublisher(controller=aries_controller, logger=logger)

    logger.debug("Asserting governance agent is host being called")
    if aries_controller.configuration.host != GOVERNANCE_AGENT_URL:
        raise CloudApiException(
            "Only governance agents are allowed to access this endpoint.",
            status_code=403,
        )

    schema_request = handle_model_with_validation(
        logger=bound_logger,
        model_class=SchemaSendRequest,
        attributes=schema.attribute_names,
        schema_name=schema.name,
        schema_version=schema.version,
    )

    result = await publisher.publish_schema(schema_request)

    result = credential_schema_from_acapy(result.sent.var_schema)
    bound_logger.info("Successfully published and registered schema.")
    return result


async def get_schemas_as_tenant(
    aries_controller: AcaPyClient,
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
) -> List[CredentialSchema]:
    """
    Allows tenants to get all schemas from trust registry
    """
    bound_logger = logger.bind(
        body={
            "schema_id": schema_id,
            "schema_issuer_did": schema_issuer_did,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }
    )
    bound_logger.debug("Fetching schemas from trust registry")

    if schema_id:  # fetch specific id
        trust_registry_schemas = [await get_trust_registry_schema_by_id(schema_id)]
    else:  # client is not filtering by schema_id, fetch all
        trust_registry_schemas = await get_trust_registry_schemas()

    schema_ids = [schema.id for schema in trust_registry_schemas]

    bound_logger.debug("Getting schemas associated with fetched ids")
    schemas = await get_schemas_by_id(
        aries_controller=aries_controller,
        schema_ids=schema_ids,
    )

    if schema_issuer_did:
        schemas = [
            schema for schema in schemas if schema.id.split(":")[0] == schema_issuer_did
        ]
    if schema_name:
        schemas = [schema for schema in schemas if schema.name == schema_name]
    if schema_version:
        schemas = [schema for schema in schemas if schema.version == schema_version]

    return schemas


async def get_schemas_as_governance(
    aries_controller: AcaPyClient,
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
) -> List[CredentialSchema]:
    """
    Governance agents gets all schemas created by itself
    """
    bound_logger = logger.bind(
        body={
            "schema_id": schema_id,
            "schema_issuer_did": schema_issuer_did,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }
    )

    logger.debug("Asserting governance agent is host being called")
    if aries_controller.configuration.host != GOVERNANCE_AGENT_URL:
        raise CloudApiException(
            "Only governance agents are allowed to access this endpoint.",
            status_code=403,
        )

    # Get all created schema ids that match the filter
    bound_logger.debug("Fetching created schemas")
    response = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=aries_controller.schema.get_created_schemas,
        schema_id=schema_id,
        schema_issuer_did=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )

    # Initiate retrieving all schemas
    schema_ids = response.schema_ids or []

    bound_logger.debug("Getting schemas associated with fetched ids")
    schemas = await get_schemas_by_id(
        aries_controller=aries_controller,
        schema_ids=schema_ids,
    )

    return schemas


async def get_schemas_by_id(
    aries_controller: AcaPyClient,
    schema_ids: List[str],
) -> List[CredentialSchema]:
    """
    Fetch schemas with attributes using schema IDs.
    The following logic applies to both governance and tenant calls.
    Retrieve the relevant schemas from the ledger:
    """
    logger.debug("Fetching schemas from schema ids")

    get_schema_futures = [
        handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.schema.get_schema,
            schema_id=schema_id,
        )
        for schema_id in schema_ids
    ]

    # Wait for completion of futures
    if get_schema_futures:
        logger.debug("Fetching each of the created schemas")
        schema_results: List[SchemaGetResult] = await asyncio.gather(
            *get_schema_futures
        )
    else:
        logger.debug("No created schema ids returned")
        schema_results = []

    # transform all schemas into response model (if schemas returned)
    schemas = [
        credential_schema_from_acapy(schema.var_schema)
        for schema in schema_results
        if schema.var_schema
    ]

    return schemas

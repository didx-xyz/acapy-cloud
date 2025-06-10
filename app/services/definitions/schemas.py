import asyncio

from aries_cloudcontroller import (
    AcaPyClient,
    AnonCredsSchema,
    GetSchemaResult,
    SchemaPostOption,
    SchemaPostRequest,
)

from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.definitions import CreateSchema, CredentialSchema, SchemaType
from app.routes.trust_registry import get_schemas as get_trust_registry_schemas
from app.services.definitions.schema_publisher import SchemaPublisher
from app.util.definitions import anoncreds_schema_from_acapy
from app.util.did import strip_qualified_did_sov
from shared.constants import GOVERNANCE_AGENT_URL
from shared.log_config import get_logger

logger = get_logger(__name__)


async def create_schema(
    aries_controller: AcaPyClient,
    schema: CreateSchema,
    public_did: str | None = None,  # Required for anoncreds schemas
) -> CredentialSchema:
    """Create a schema and register it in the trust registry

    NB: Auth is handled in the route, so we assume the request is valid:
    - AnonCreds schemas are only created by governance agents
    """
    bound_logger = logger.bind(body=schema)
    publisher = SchemaPublisher(controller=aries_controller, logger=logger)

    if schema.schema_type == SchemaType.ANONCREDS:
        assert public_did is not None, "Public DID is required for AnonCreds schemas"
        anoncreds_schema = handle_model_with_validation(
            logger=bound_logger,
            model_class=AnonCredsSchema,
            attr_names=schema.attribute_names,
            name=schema.name,
            version=schema.version,
            issuer_id=strip_qualified_did_sov(public_did),
            # See the reason for stripping did:sov from the issuer DID here:
            # https://github.com/openwallet-foundation/acapy/issues/3540#issuecomment-2686157016
        )

        schema_request = handle_model_with_validation(
            logger=bound_logger,
            model_class=SchemaPostRequest,
            var_schema=anoncreds_schema,
            options=SchemaPostOption(create_transaction_for_endorser=False),
        )

        result = await publisher.publish_anoncreds_schema(schema_request)
    else:
        raise NotImplementedError("Only AnonCreds schemas are supported")

    bound_logger.debug("Successfully published and registered schema.")
    return result


async def get_schemas_as_tenant(
    aries_controller: AcaPyClient,
    schema_issuer_did: str | None = None,
    schema_name: str | None = None,
    schema_version: str | None = None,
) -> list[CredentialSchema]:
    """Allows tenants to get all schemas from trust registry"""
    bound_logger = logger.bind(
        body={
            "schema_issuer_did": schema_issuer_did,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }
    )
    bound_logger.debug("Fetching schemas from trust registry")
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
    schema_issuer_did: str | None = None,
    schema_name: str | None = None,
    schema_version: str | None = None,
) -> list[CredentialSchema]:
    """Governance agents gets all schemas created by itself"""
    bound_logger = logger.bind(
        body={
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
        acapy_call=aries_controller.anoncreds_schemas.get_schemas,
        schema_issuer_id=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )

    # Initiate retrieving all schemas
    schema_ids = response.schema_ids or []

    bound_logger.debug("Getting schemas associated with fetched ids")
    schemas = await get_schemas_by_id(
        aries_controller=aries_controller, schema_ids=schema_ids
    )

    return schemas


async def get_schemas_by_id(
    aries_controller: AcaPyClient,
    schema_ids: list[str],
) -> list[CredentialSchema]:
    """Fetch schemas with attributes using schema IDs.
    The following logic applies to both governance and tenant calls.
    Retrieve the relevant schemas from the ledger:
    """
    logger.debug("Fetching schemas from anoncreds wallet")
    get_schema_futures = [
        handle_acapy_call(
            logger=logger,
            acapy_call=aries_controller.anoncreds_schemas.get_schema,
            schema_id=schema_id,
        )
        for schema_id in schema_ids
    ]

    # Wait for completion of futures
    if get_schema_futures:
        logger.debug("Fetching each of the created schemas")
        schema_results: list[GetSchemaResult] = await asyncio.gather(
            *get_schema_futures
        )
    else:
        logger.debug("No created schema ids returned")
        schema_results = []

    # transform all schemas into response model (if schemas returned)
    schemas = [
        anoncreds_schema_from_acapy(schema)
        for schema in schema_results
        if schema.var_schema
    ]

    return schemas

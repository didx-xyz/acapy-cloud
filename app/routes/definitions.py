from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

import app.services.definitions.credential_definitions as cred_def_service
import app.services.definitions.schemas as schemas_service
from app.dependencies.acapy_clients import client_from_auth, get_governance_controller
from app.dependencies.auth import (
    AcaPyAuth,
    AcaPyAuthVerified,
    acapy_auth_from_header,
    acapy_auth_governance,
    acapy_auth_verified,
)
from app.dependencies.role import Role
from app.exceptions import handle_acapy_call
from app.exceptions.cloudapi_exception import CloudApiException
from app.models.definitions import (
    CreateCredentialDefinition,
    CreateSchema,
    CredentialDefinition,
    CredentialSchema,
)
from app.util.definitions import (
    anoncreds_schema_from_acapy,
    credential_definition_from_acapy,
    credential_schema_from_acapy,
)
from app.util.retry_method import coroutine_with_retry
from app.util.wallet_type_checks import get_wallet_type
from shared.log_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/v1/definitions",
    tags=["definitions"],
)


@router.post("/schemas", summary="Create a new Schema", response_model=CredentialSchema)
async def create_schema(
    schema: CreateSchema,
    # Only governance can create schemas
    governance_auth: AcaPyAuthVerified = Depends(acapy_auth_governance),
) -> CredentialSchema:
    """
    Create and publish a new schema to the ledger
    ---
    **NB**: Only governance can create schemas.

    A schema is used to create credential definitions, which is used for issuing credentials.
    The schema defines the attributes that can exist in that credential.

    When a schema is created, it is published to the ledger and written to our public trust registry,
    so that everyone in the ecosystem can view schemas that are valid and available.

    Request Body:
    ---
        body: CreateSchema
            name: str
                The name of the schema.
            version: str
                The version of the schema.
            attribute_names: List[str]
                The attribute names of the schema.

    Returns:
    ---
        CredentialSchema
            The created schema object
    """
    bound_logger = logger.bind(body=schema)
    bound_logger.debug("POST request received: Create schema (publish and register)")

    async with get_governance_controller(governance_auth) as aries_controller:
        schema_response = await schemas_service.create_schema(
            aries_controller=aries_controller,
            schema=schema,
        )
    return schema_response


@router.get(
    "/schemas",
    summary="Get Created Schemas",
    response_model=List[CredentialSchema],
)
async def get_schemas(
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> List[CredentialSchema]:
    """
    Get created schemas
    ---
    All tenants can call this endpoint to view available schemas.

    If governance calls this endpoint, it will return all the schemas created by governance
    (whether the schemas are on the trust registry or not).

    If tenants call this endpoint, it will return all schemas on the trust registry.
    The difference between this endpoint and the public trust registry endpoint, is that this response includes
    the attribute information of the schemas.

    Results can be filtered by the parameters listed below.

    Parameters (Optional):
    ---
        schema_issuer_did: str
        schema_name: str
        schema_version: str

    Returns:
    ---
        List[CredentialSchema]
            A list of created schemas
    """
    is_governance = auth.role == Role.GOVERNANCE
    bound_logger = logger.bind(
        body={
            "is_governance": is_governance,
            "schema_issuer_did": schema_issuer_did,
            "schema_name": schema_name,
            "schema_version": schema_version,
        }
    )
    bound_logger.debug("GET request received: Get created schemas")

    async with client_from_auth(auth) as aries_controller:
        if not is_governance:  # regular tenant is calling endpoint
            schemas = await schemas_service.get_schemas_as_tenant(
                aries_controller=aries_controller,
                schema_issuer_did=schema_issuer_did,
                schema_name=schema_name,
                schema_version=schema_version,
            )
        else:  # Governance is calling the endpoint
            try:
                schemas = await schemas_service.get_schemas_as_governance(
                    aries_controller=aries_controller,
                    schema_issuer_did=schema_issuer_did,
                    schema_name=schema_name,
                    schema_version=schema_version,
                )
            except CloudApiException as e:
                bound_logger.error("Failed to get schemas. Error: {}", e)
                raise

    if schemas:
        bound_logger.debug("Successfully fetched schemas.")
    else:
        bound_logger.debug("No schemas matching request.")

    return schemas


@router.get(
    "/schemas/{schema_id}",
    summary="Get a Schema",
    response_model=CredentialSchema,
)
async def get_schema(
    schema_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialSchema:
    """
    Retrieve schema by id
    ---
    This endpoint fetches a schema from the ledger, using the schema_id.

    Any tenant can call this endpoint to retrieve a schema.
    This endpoint will list all the attributes of the schema.

    Parameters:
    ---
        schema_id: str
            schema id

    Returns:
    ---
        CredentialSchema
            The schema object
    """
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("GET request received: Get schema by id")
    is_governance = auth.role == Role.GOVERNANCE

    async with client_from_auth(auth) as aries_controller:
        if is_governance:
            # Get the wallet type from the server config
            server_config = await aries_controller.server.get_config()
            wallet_type = server_config.config.get("wallet.type")
        else:
            wallet_type = await get_wallet_type(
                aries_controller=aries_controller,
                logger=bound_logger,
            )

        if wallet_type == "askar-anoncreds":
            schema = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.anoncreds_schemas.get_schema,
                schema_id=schema_id,
            )

            if not schema.var_schema:
                raise HTTPException(404, f"Schema with id {schema_id} not found.")

            result = anoncreds_schema_from_acapy(schema)
        elif wallet_type == "askar":
            schema = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.schema.get_schema,
                schema_id=schema_id,
            )

            if not schema.var_schema:
                raise HTTPException(404, f"Schema with id {schema_id} not found.")

            result = credential_schema_from_acapy(schema.var_schema)
        else:
            # Should never happen
            raise HTTPException(500, "Unknown wallet type")

    bound_logger.debug("Successfully fetched schema by id.")
    return result


@router.post(
    "/credentials",
    summary="Create a new Credential Definition",
    response_model=CredentialDefinition,
)
async def create_credential_definition(
    credential_definition: CreateCredentialDefinition,
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
) -> CredentialDefinition:
    """
    Create a credential definition
    ---
    Only issuers can create credential definitions.

    A credential definition essentially builds off a schema, which defines the attributes that can belong to a
    credential, and it specifies whether credentials using this definition are revocable or not.

    **NB**: If revocation is requested (`"support_revocation": true`), then revocation registries will be created.
    The creation of these revocation registries can take up to one minute.

    Request Body:
    ---
        body: CreateCredentialDefinition
            schema_id: str
                The id of the schema to use for this credential definition.
            tag: str
                The label to use for the credential definition.
            support_revocation: bool
                Whether you want credentials using this definition to be revocable or not

    Returns:
    ---
        CredentialDefinition
            The created credential definition
    """
    bound_logger = logger.bind(
        body={
            "schema_id": credential_definition.schema_id,
            "tag": credential_definition.tag,
            "support_revocation": credential_definition.support_revocation,
        }
    )
    bound_logger.debug("POST request received: Create credential definition")

    support_revocation = credential_definition.support_revocation

    async with client_from_auth(auth) as aries_controller:
        credential_definition_id = await cred_def_service.create_credential_definition(
            aries_controller=aries_controller,
            credential_definition=credential_definition,
            support_revocation=support_revocation,
        )

    # ACA-Py only returns the id after creating a credential definition
    # We want consistent return types across all endpoints, so retrieving the credential
    # definition here.

    # Retry logic to avoid race condition, as it can return 404
    result = await coroutine_with_retry(
        coroutine_func=get_credential_definition_by_id,
        args=(credential_definition_id, auth),
        logger=bound_logger,
        max_attempts=3,
        retry_delay=0.5,
    )
    bound_logger.debug("Successfully created credential definition.")
    return result


@router.get(
    "/credentials",
    summary="Get Created Credential Definitions",
    response_model=List[CredentialDefinition],
)
async def get_credential_definitions(
    issuer_did: Optional[str] = None,
    credential_definition_id: Optional[str] = None,
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> List[CredentialDefinition]:
    """
    Get credential definitions created by the tenant
    ---
    This endpoint returns all credential definitions created by the tenant. Only issuers can create
    credential definitions, and so only issuers will get results from this endpoint.

    The results can be filtered by the parameters listed below.

    Parameters (Optional):
    ---
        issuer_did: str
        credential_definition_id: str
        schema_id: str
        schema_issuer_id: str
        schema_version: str

    Returns:
    ---
        List[CredentialDefinition]
            A list of created credential definitions
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
    bound_logger.debug(
        "GET request received: Get credential definitions created by agent"
    )

    # Get all created credential definition ids that match the filter
    async with client_from_auth(auth) as aries_controller:
        credential_definitions = await cred_def_service.get_credential_definitions(
            aries_controller=aries_controller,
            issuer_did=issuer_did,
            credential_definition_id=credential_definition_id,
            schema_id=schema_id,
            schema_issuer_did=schema_issuer_did,
            schema_name=schema_name,
            schema_version=schema_version,
        )

    if credential_definitions:
        bound_logger.debug("Successfully fetched credential definitions.")
    else:
        bound_logger.debug("No credential definitions matching request.")

    return credential_definitions


@router.get(
    "/credentials/{credential_definition_id}",
    summary="Get a Credential Definition",
    response_model=CredentialDefinition,
)
async def get_credential_definition_by_id(
    credential_definition_id: str,
    auth: AcaPyAuth = Depends(acapy_auth_from_header),
) -> CredentialDefinition:
    """
    Get credential definition by id
    ---
    This endpoint returns information for a credential definition.

    Anyone can call this, whether they created the requested credential definition or not.
    Practically it will just reveal the schema that was used for the credential definition.

    Parameters:
    ---
        credential_definition_id: str
            credential definition id

    Returns:
    ---
        CredentialDefinition
            The credential definition
    """
    bound_logger = logger.bind(
        body={"credential_definition_id": credential_definition_id}
    )
    bound_logger.debug("GET request received: Get credential definition by id")

    async with client_from_auth(auth) as aries_controller:
        wallet_type = await get_wallet_type(
            aries_controller=aries_controller,
            logger=bound_logger,
        )

        bound_logger.debug("Getting credential definition")
        if wallet_type == "askar-anoncreds":
            credential_definition = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.anoncreds_credential_definitions.get_credential_definition,
                cred_def_id=credential_definition_id,
            )
        else:  # wallet_type == "askar"
            credential_definition = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=aries_controller.credential_definition.get_cred_def,
                cred_def_id=credential_definition_id,
            )

        if not credential_definition:
            raise HTTPException(
                404,
                f"Credential Definition with id {credential_definition_id} not found.",
            )

        bound_logger.debug("Cast credential definition response to model")
        cloudapi_credential_definition = credential_definition_from_acapy(
            credential_definition
            if wallet_type == "askar-anoncreds"
            else credential_definition.credential_definition
        )

        # We need to update the schema_id on the returned credential definition as
        # ACA-Py returns the schema_id as the seq_no
        bound_logger.debug("Fetching schema associated with definition's schema id")
        schema = await get_schema(  # TODO: Avoid using endpoint method here
            schema_id=cloudapi_credential_definition.schema_id,
            auth=auth,
        )
        cloudapi_credential_definition.schema_id = schema.id

    bound_logger.debug("Successfully fetched credential definition.")
    return cloudapi_credential_definition

import asyncio
import json
import logging
from typing import List, Optional

from aiohttp import ClientResponseError
from aries_cloudcontroller import AcaPyClient
from aries_cloudcontroller import \
    CredentialDefinition as AcaPyCredentialDefinition
from aries_cloudcontroller import (ModelSchema, RevRegUpdateTailsFileUri,
                                   SchemaSendRequest)
from aries_cloudcontroller.model.credential_definition_send_request import \
    CredentialDefinitionSendRequest
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.constants import ACAPY_ENDORSER_ALIAS, ACAPY_TAILS_SERVER_BASE_URL
from app.dependencies import (AcaPyAuthVerified, acapy_auth_verified,
                              agent_role, agent_selector,
                              get_governance_controller)
from app.error.cloud_api_error import CloudApiException
from app.facades import acapy_wallet, trust_registry
from app.facades.revocation_registry import (
    create_revocation_registry, publish_revocation_registry_on_ledger)
from app.listener import Listener
from app.role import Role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/generic/definitions",
    tags=["definitions"],
)


class CreateCredentialDefinition(BaseModel):
    tag: str = Field(..., example="default")
    schema_id: str = Field(..., example="CXQseFxV34pcb8vf32XhEa:2:test_schema:0.3")
    support_revocation: bool = Field(default=True)
    revocation_registry_size: int = Field(default=32767)


class CredentialDefinition(BaseModel):
    id: str = Field(..., example="5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:default")
    tag: str = Field(..., example="default")
    schema_id: str = Field(..., example="CXQseFxV34pcb8vf32XhEa:2:test_schema:0.3")


class CreateSchema(BaseModel):
    name: str = Field(..., example="test_schema")
    version: str = Field(..., example="0.3.0")
    attribute_names: List[str] = Field(..., example=["speed"])


class CredentialSchema(BaseModel):
    id: str = Field(..., example="CXQseFxV34pcb8vf32XhEa:2:test_schema:0.3")
    name: str = Field(..., example="test_schema")
    version: str = Field(..., example="0.3.0")
    attribute_names: List[str] = Field(..., example=["speed"])


def _credential_schema_from_acapy(schema: ModelSchema):
    return CredentialSchema(
        id=schema.id,
        name=schema.name,
        version=schema.version,
        attribute_names=schema.attr_names,
    )


def _credential_definition_from_acapy(credential_definition: AcaPyCredentialDefinition):
    return CredentialDefinition(
        id=credential_definition.id,
        tag=credential_definition.tag,
        schema_id=credential_definition.schema_id,
    )


@router.get("/credentials", response_model=List[CredentialDefinition])
async def get_credential_definitions(
    issuer_did: Optional[str] = None,
    credential_definition_id: Optional[str] = None,
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    aries_controller: AcaPyClient = Depends(agent_selector),
) -> List[CredentialDefinition]:
    """
        Get agent-created credential definitions

    Parameters:
    ---
        issuer_did: Optional[str]
        credential_definition_id: Optional[str]
        schema_id: Optional[str]
        schema_issuer_id: Optional[str]
        schema_version: Optional[str]

    Returns:
    ---
        Created credential definitions
    """
    # Get all created credential definition ids that match the filter
    response = await aries_controller.credential_definition.get_created_cred_defs(
        issuer_did=issuer_did,
        cred_def_id=credential_definition_id,
        schema_id=schema_id,
        schema_issuer_did=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )

    # Initiate retrieving all credential definitions
    credential_definition_ids = response.credential_definition_ids or []
    get_credential_definition_futures = [
        aries_controller.credential_definition.get_cred_def(
            cred_def_id=credential_definition_id
        )
        for credential_definition_id in credential_definition_ids
    ]

    # Wait for completion of retrieval and transform all credential definitions
    # into response model (if a credential definition was returned)
    credential_definition_results = await asyncio.gather(
        *get_credential_definition_futures
    )
    credential_definitions = [
        _credential_definition_from_acapy(credential_definition.credential_definition)
        for credential_definition in credential_definition_results
        if credential_definition.credential_definition
    ]

    return credential_definitions


@router.get(
    "/credentials/{credential_definition_id}", response_model=CredentialDefinition
)
async def get_credential_definition_by_id(
    credential_definition_id: str,
    aries_controller: AcaPyClient = Depends(agent_selector),
) -> CredentialDefinition:
    """
        Get credential definition by id.

    Parameters:
    -----------
        credential_definition_id: str
            credential definition id

    """
    credential_definition = await aries_controller.credential_definition.get_cred_def(
        cred_def_id=credential_definition_id
    )

    if not credential_definition.credential_definition:
        raise HTTPException(
            404, f"Credential Definition with id {credential_definition_id} not found"
        )

    cloudapi_credential_definition = _credential_definition_from_acapy(
        credential_definition.credential_definition
    )

    # We need to update the schema_id on the returned credential definition as
    # ACA-Py returns the schema_id as the seq_no
    schema = await get_schema(
        schema_id=cloudapi_credential_definition.schema_id,
        aries_controller=aries_controller,
    )
    cloudapi_credential_definition.schema_id = schema.id

    return cloudapi_credential_definition


@router.post("/credentials", response_model=CredentialDefinition)
async def create_credential_definition(
    credential_definition: CreateCredentialDefinition,
    aries_controller: AcaPyClient = Depends(agent_selector),
    auth: AcaPyAuthVerified = Depends(acapy_auth_verified),
) -> CredentialDefinition:
    """
        Create a credential definition.

    Parameters:
    -----------
        credential_definition: CreateCredentialDefinition
            Payload for creating a credential definition.

    Returns:
    --------
        Credential Definition
    """

    # Assert the agent has a public did
    public_did = await acapy_wallet.assert_public_did(aries_controller)

    # Make sure we are allowed to issue this schema according to trust registry rules
    await trust_registry.assert_valid_issuer(
        public_did, credential_definition.schema_id
    )

    listener = Listener(topic="endorsements", wallet_id=auth.wallet_id)

    result = await aries_controller.credential_definition.publish_cred_def(
        body=CredentialDefinitionSendRequest(
            schema_id=credential_definition.schema_id,
            support_revocation=credential_definition.support_revocation,
            tag=credential_definition.tag,
        )
    )

    if result.txn and result.txn.transaction_id:
        try:
            # Wait for transaction to be acknowledged and written to the ledger
            await listener.wait_for_filtered_event(
                filter_map={
                    "state": "transaction-acked",
                    "transaction_id": result.txn.transaction_id,
                }
            )
        except asyncio.TimeoutError:
            raise CloudApiException(
                "Timeout waiting for endorser to accept the endorsement request", 504
            )
        finally:
            listener.stop()

        try:
            transaction = await aries_controller.endorse_transaction.get_transaction(
                tran_id=result.txn.transaction_id
            )

            # Based on
            # https://github.com/bcgov/traction/blob/6c86d35f3e8b8ca0b88a198876155ba820fb34ea/services/traction/api/services/SchemaWorkflow.py#L276-L280
            signatures = transaction.signature_response[0]["signature"]
            endorser_public_did = list(signatures.keys())[0]
            signature = json.loads(signatures[endorser_public_did])

            public_did = signature["identifier"]
            sig_type = signature["operation"]["signature_type"]
            schema_ref = signature["operation"]["ref"]
            tag = signature["operation"]["tag"]
            credential_definition_id = f"{public_did}:3:{sig_type}:{schema_ref}:{tag}"
        except Exception as e:
            raise CloudApiException(
                "Unable to construct credential definition id from signature response"
            ) from e
    elif result.sent and result.sent.credential_definition_id:
        credential_definition_id = result.sent.credential_definition_id
    else:
        raise CloudApiException(
            "Missing both `credential_definition_id` and `transaction_id` from response after publishing cred def"
        )

    if credential_definition.support_revocation:
        try:
            # Create a revocation registry and publish it on the ledger
            revoc_reg_creation_result = await create_revocation_registry(
                controller=aries_controller,
                credential_definition_id=credential_definition_id,
                max_cred_num=credential_definition.revocation_registry_size,
            )
            await aries_controller.revocation.update_registry(
                rev_reg_id=revoc_reg_creation_result.revoc_reg_id,
                body=RevRegUpdateTailsFileUri(
                    tails_public_uri=f"{ACAPY_TAILS_SERVER_BASE_URL}/{revoc_reg_creation_result.revoc_reg_id}"
                ),
            )
            endorser_connection = await aries_controller.connection.get_connections(
                alias=ACAPY_ENDORSER_ALIAS
            )
            # NOTE: Special case - the endorser registers a cred def itself that
            # supports revocation so there is no endorser connection.
            # Otherwise onboarding should have created an endorser connection
            # for tenants so this fails correctly
            has_connections = len(endorser_connection.results) > 0
            await publish_revocation_registry_on_ledger(
                controller=aries_controller,
                revocation_registry_id=revoc_reg_creation_result.revoc_reg_id,
                connection_id=endorser_connection.results[0].connection_id
                if has_connections
                else None,
                create_transaction_for_endorser=has_connections,
            )
            if has_connections:
                admin_listener = Listener(topic="endorsements", wallet_id="admin")
                async with get_governance_controller() as endorser_controller:
                    try:
                        txn_record = await admin_listener.wait_for_filtered_event(
                            filter_map={
                                "state": "request-received",
                            }
                        )
                    except TimeoutError:
                        raise CloudApiException(
                            "Timeout occurred while waiting to retrieve transaction record for endorser",
                            504,
                        )
                    finally:
                        admin_listener.stop()

                    await endorser_controller.endorse_transaction.endorse_transaction(
                        tran_id=txn_record["transaction_id"]
                    )

            active_rev_reg = await aries_controller.revocation.set_registry_state(
                rev_reg_id=revoc_reg_creation_result.revoc_reg_id, state="active"
            )
            credential_definition_id = active_rev_reg.result.cred_def_id
        except ClientResponseError as e:
            logger.debug(
                "A ClientResponseError was caught while supporting revocation. The error message is: '%s'",
                e.message,
            )
            raise e

    # ACA-Py only returns the id after creating a credential definition
    # We want consistent return types across all endpoints, so retrieving the credential
    # definition here.
    return await get_credential_definition_by_id(
        credential_definition_id, aries_controller
    )


@router.get("/schemas", response_model=List[CredentialSchema])
async def get_schemas(
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    aries_controller: AcaPyClient = Depends(agent_selector),
) -> List[CredentialSchema]:
    """
        Retrieve schemas that the current agent created.

    Parameters:
    -----------
        schema_id: str (Optional)
        schema_issuer_did: str (Optional)
        schema_name: str (Optional)
        schema_version: str (Optional)

    Returns:
    --------
        son response with created schemas from ledger.
    """
    # Get all created schema ids that match the filter
    response = await aries_controller.schema.get_created_schemas(
        schema_id=schema_id,
        schema_issuer_did=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )

    # Initiate retrieving all schemas
    schema_ids = response.schema_ids or []
    get_schema_futures = [
        aries_controller.schema.get_schema(schema_id=schema_id)
        for schema_id in schema_ids
    ]

    # Wait for completion of retrieval and transform all schemas into response model (if a schema was returned)
    schema_results = await asyncio.gather(*get_schema_futures)
    schemas = [
        _credential_schema_from_acapy(schema.schema_)
        for schema in schema_results
        if schema.schema_
    ]

    return schemas


@router.get("/schemas/{schema_id}", response_model=CredentialSchema)
async def get_schema(
    schema_id: str,
    aries_controller: AcaPyClient = Depends(agent_selector),
) -> CredentialSchema:
    """
        Retrieve schema by id.

    Parameters:
    -----------
        schema_id: str
            schema id
    """
    schema = await aries_controller.schema.get_schema(schema_id=schema_id)

    if not schema.schema_:
        raise HTTPException(404, f"Schema with id {schema_id} not found")

    return _credential_schema_from_acapy(schema.schema_)


@router.post("/schemas", response_model=CredentialSchema)
async def create_schema(
    schema: CreateSchema,
    # Only governance can create schemas
    aries_controller: AcaPyClient = Depends(agent_role(Role.GOVERNANCE)),
) -> CredentialSchema:
    """
        Create a new schema.

    Parameters:
    ------------
        schema: CreateSchema
            Payload for creating a schema.

    Returns:
    --------
        The response object from creating a schema.
    """
    schema_send_request = SchemaSendRequest(
        attributes=schema.attribute_names,
        schema_name=schema.name,
        schema_version=schema.version,
    )
    try:
        result = await aries_controller.schema.publish_schema(
            body=schema_send_request, create_transaction_for_endorser=False
        )
    except ClientResponseError as e:
        if e.status == 400 and "already exist" in e.message:
            pub_did = await aries_controller.wallet.get_public_did()
            _schema = await aries_controller.schema.get_schema(
                schema_id=f"{pub_did.result.did}:2:{schema.name}:{schema.version}"
            )
            # Edge case where the governance agent has changed its public did
            # Then we need to retrieve the schema in a different way as constructing the schema ID the way above
            # will not be correct due to different public did.
            if _schema.schema_ is None:
                schemas_created_ids = await aries_controller.schema.get_created_schemas(
                    schema_name=schema.name, schema_version=schema.version
                )
                schemas = [
                    await aries_controller.schema.get_schema(schema_id=schema_id)
                    for schema_id in schemas_created_ids.schema_ids
                    if schema_id is not None
                ]
                if len(schemas) > 1:
                    raise CloudApiException(
                        f"Multiple schemas with name {schema.name} and version {schema.version} exist."
                        + f"These are: {str(schemas_created_ids.schema_ids)}",
                        409,
                    )
                _schema = schemas[0]
            # Schema exists with different attributes
            if set(_schema.schema_.attr_names) != set(schema.attribute_names):
                raise CloudApiException(
                    "Error creating schema: Schema already exists with different attribute names."
                    + f"Given: {str(set(_schema.schema_.attr_names))}. Found: {str(set(schema.attribute_names))}",
                    409,
                )
            return _credential_schema_from_acapy(_schema.schema_)
        else:
            logger.warning(
                "An unhandled ClientResponseError was caught while publishing schema. The error message is: '%s'",
                e.message,
            )
            raise CloudApiException("Error while creating schema.") from e

    # Register the schema in the trust registry
    try:
        if result.sent and result.sent.schema_id:
            await trust_registry.register_schema(schema_id=result.sent.schema_id)
        else:
            raise CloudApiException("No SchemaSendResult in publish_schema response")
    except trust_registry.TrustRegistryException as error:
        # If status_code is 405 it means the schema already exists in the trust registry
        # That's okay, because we've achieved our intended result:
        #   make sure the schema is registered in the trust registry
        if error.status_code != 400:
            raise error

    return _credential_schema_from_acapy(result.sent.schema_)

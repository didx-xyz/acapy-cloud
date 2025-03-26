import asyncio
from logging import Logger
from typing import List

from aries_cloudcontroller import (
    AcaPyClient,
    GetSchemaResult,
    SchemaGetResult,
    SchemaPostRequest,
    SchemaSendRequest,
)

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.definitions import CredentialSchema
from app.services.trust_registry.schemas import register_schema
from app.util.definitions import (
    anoncreds_credential_schema,
    credential_schema_from_acapy,
)
from app.util.retry_method import coroutine_with_retry_until_value


class SchemaPublisher:
    def __init__(self, controller: AcaPyClient, logger: Logger):
        self._logger = logger
        self._controller = controller

    async def publish_schema(
        self, schema_request: SchemaSendRequest
    ) -> CredentialSchema:
        try:
            result = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.schema.publish_schema,
                body=schema_request,
                create_transaction_for_endorser=False,
            )
        except CloudApiException as e:
            if "already exist" in e.detail and e.status_code == 400:
                result = await self._handle_existing_schema(schema_request)
                return result
            else:
                self._logger.warning(
                    "An unhandled Exception was caught while publishing schema: {}",
                    e.detail,
                )
                raise CloudApiException("Error while creating schema.") from e

        if result.sent and result.sent.schema_id:
            await register_schema(schema_id=result.sent.schema_id)
        else:
            self._logger.error("No SchemaSendResult in `publish_schema` response.")
            raise CloudApiException(
                "An unexpected error occurred: could not publish schema."
            )

        result = credential_schema_from_acapy(result.sent.var_schema)
        return result

    async def _handle_existing_schema(
        self, schema: SchemaSendRequest
    ) -> CredentialSchema:
        self._logger.info("Handling case of schema already existing on ledger")
        self._logger.debug("Fetching public DID for governance controller")
        pub_did = await handle_acapy_call(
            logger=self._logger,
            acapy_call=self._controller.wallet.get_public_did,
        )

        _schema_id = (
            f"{pub_did.result.did}:2:{schema.schema_name}:{schema.schema_version}"
        )
        self._logger.debug(
            "Fetching schema id `{}` which is associated with request",
            _schema_id,
        )

        _schema: SchemaGetResult = await handle_acapy_call(
            logger=self._logger,
            acapy_call=self._controller.schema.get_schema,
            schema_id=_schema_id,
        )

        # Edge case where the governance agent has changed its public did
        # Then we need to retrieve the schema in a different way as constructing
        # the schema ID the way above will not be correct due to different public did.
        if _schema.var_schema is None:
            self._logger.debug(
                "Schema not found. Governance agent may have changed public DID. "
                "Fetching schemas created by governance with requested name and version"
            )
            schemas_created_ids = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.schema.get_created_schemas,
                schema_name=schema.schema_name,
                schema_version=schema.schema_version,
            )
            self._logger.debug("Getting schemas associated with fetched ids")
            schemas: List[SchemaGetResult] = [
                await handle_acapy_call(
                    logger=self._logger,
                    acapy_call=self._controller.schema.get_schema,
                    schema_id=schema_id,
                )
                for schema_id in schemas_created_ids.schema_ids
                if schema_id
            ]

            if not schemas:
                raise CloudApiException("Could not publish schema.", 500)
            if len(schemas) > 1:
                error_message = (
                    f"Multiple schemas with name {schema.schema_name} "
                    f"and version {schema.schema_version} exist."
                    f"These are: `{str(schemas_created_ids.schema_ids)}`."
                )
                raise CloudApiException(error_message, 409)
            self._logger.debug("Using updated schema id with new DID")
            _schema: SchemaGetResult = schemas[0]

        # Schema exists with different attributes
        if set(_schema.var_schema.attr_names) != set(schema.attributes):
            error_message = (
                "Error creating schema: Schema already exists with different attribute "
                f"names. Given: `{str(set(schema.attributes))}`. "
                f"Found: `{str(set(_schema.var_schema.attr_names))}`."
            )
            raise CloudApiException(error_message, 409)

        result = credential_schema_from_acapy(_schema.var_schema)
        self._logger.debug(
            "Schema already exists on ledger. Returning schema definition: `{}`.",
            result,
        )
        return result

    async def publish_anoncreds_schema(
        self,
        schema_request: SchemaPostRequest,
        retry_sleep_duration: int = 2,
        max_retries: int = 15,
    ) -> CredentialSchema:
        try:
            schema_result = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.anoncreds_schemas.create_schema,
                body=schema_request,
            )
        except CloudApiException as e:
            if "already exist" in e.detail and e.status_code == 400:
                schema_result = await self._handle_existing_anoncreds_schema(
                    schema_request
                )
                return schema_result
            else:
                self._logger.warning(
                    "An unhandled Exception was caught while publishing schema: {}",
                    e.detail,
                )
                raise CloudApiException("Error while creating schema.") from e

        if schema_result.schema_state and schema_result.schema_state.schema_id:
            schema_id = schema_result.schema_state.schema_id
        else:
            self._logger.error(
                "Did not get expected schema_id in `publish_schema` response: {}.",
                schema_result,
            )
            raise CloudApiException(
                "An unexpected error occurred: could not publish schema."
            )

        state = schema_result.schema_state.state
        if state not in ("finished", "wait"):
            self._logger.error("Schema state is `{}`. This should not happen.", state)
            raise CloudApiException(
                "An unexpected error occurred: could not publish schema.",
            )

        if state == "wait":  # expected, since we require endorsement
            transaction = schema_result.registration_metadata.get("txn")
            transaction_id = transaction.get("transaction_id") if transaction else None

            if not transaction_id:
                self._logger.error(
                    "No transaction id found in metadata: {}", schema_result
                )
                raise CloudApiException(
                    "Could not publish schema. No transaction id found in response."
                )

            try:
                await coroutine_with_retry_until_value(
                    coroutine_func=self._controller.endorse_transaction.get_transaction,
                    args=(transaction_id,),
                    field_name="state",
                    expected_value="transaction_acked",
                    logger=self._logger,
                    max_attempts=max_retries,
                    retry_delay=retry_sleep_duration,
                )
            except asyncio.TimeoutError as e:
                raise CloudApiException(
                    "Timed out waiting for schema to be published.", 504
                ) from e

        await register_schema(schema_id=schema_id)

        schema_result = anoncreds_credential_schema(schema_result.schema_state)
        return schema_result

    async def _handle_existing_anoncreds_schema(
        self, schema: SchemaPostRequest
    ) -> CredentialSchema:
        self._logger.info("Handling case of schema already existing on ledger")
        self._logger.debug("Fetching public DID for governance controller")
        pub_did = await handle_acapy_call(
            logger=self._logger,
            acapy_call=self._controller.wallet.get_public_did,
        )

        schema_id = f"{pub_did.result.did}:2:{schema.var_schema.name}:{schema.var_schema.version}"
        self._logger.debug(
            "Fetching schema id `{}` which is associated with request",
            schema_id,
        )

        fetched_schema: GetSchemaResult = await handle_acapy_call(
            logger=self._logger,
            acapy_call=self._controller.anoncreds_schemas.get_schema,
            schema_id=schema_id,
        )

        # Edge case where the governance agent has changed its public did
        # Then we need to retrieve the schema in a different way as constructing
        # the schema ID the way above will not be correct due to different public did.
        if fetched_schema.var_schema is None:
            self._logger.debug(
                "Schema not found. Governance agent may have changed public DID. "
                "Fetching schemas created by governance with requested name and version"
            )
            schemas_created_ids = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.anoncreds_schemas.get_schemas,
                schema_name=schema.var_schema.name,
                schema_version=schema.var_schema.version,
            )
            self._logger.debug("Getting schemas associated with fetched ids")
            schemas: List[GetSchemaResult] = [
                await handle_acapy_call(
                    logger=self._logger,
                    acapy_call=self._controller.anoncreds_schemas.get_schema,
                    schema_id=schema_id,
                )
                for schema_id in schemas_created_ids.schema_ids
                if schema_id
            ]

            if not schemas:
                raise CloudApiException("Could not publish schema.", 500)
            if len(schemas) > 1:
                error_message = (
                    f"Multiple schemas with name {schema.var_schema.name} "
                    f"and version {schema.var_schema.version} exist."
                    f"These are: `{str(schemas_created_ids.schema_ids)}`."
                )
                raise CloudApiException(error_message, 409)
            self._logger.debug("Using updated schema id with new DID")
            fetched_schema: GetSchemaResult = schemas[0]

        # Schema exists with different attributes
        if set(fetched_schema.var_schema.attr_names) != set(
            schema.var_schema.attr_names
        ):
            error_message = (
                "Error creating schema: Schema already exists with different attribute "
                f"names. Given: `{str(set(schema.var_schema.attr_names))}`. "
                f"Found: `{str(set(fetched_schema.var_schema.attr_names))}`."
            )
            raise CloudApiException(error_message, 409)

        result = anoncreds_credential_schema(fetched_schema)
        self._logger.debug(
            "Schema already exists on ledger. Returning schema definition: `{}`.",
            result,
        )
        return result

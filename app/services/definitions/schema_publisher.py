from logging import Logger

from aries_cloudcontroller import (
    AcaPyClient,
    GetSchemaResult,
    GetSchemasResponse,
    SchemaPostRequest,
)

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.definitions import CredentialSchema
from app.services.trust_registry.schemas import register_schema
from app.util.definitions import anoncreds_credential_schema
from app.util.retry_method import coroutine_with_retry_until_value


class SchemaPublisher:
    def __init__(self, controller: AcaPyClient, logger: Logger):
        """Initialize the schema publisher."""
        self._logger = logger
        self._controller = controller

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
            except TimeoutError as e:
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
        self._logger.debug("Fetching created schemas to find existing schema.")

        fetched_schema_ids: GetSchemasResponse = await handle_acapy_call(
            logger=self._logger,
            acapy_call=self._controller.anoncreds_schemas.get_schemas,
            schema_name=schema.var_schema.name,
            schema_version=schema.var_schema.version,
        )

        self._logger.debug(
            "Found schemas with name `{}` and version `{}`: {}",
            schema.var_schema.name,
            schema.var_schema.version,
            fetched_schema_ids,
        )

        fetch_schemas: list[GetSchemaResult] = [
            await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.anoncreds_schemas.get_schema,
                schema_id=schema_id,
            )
            for schema_id in fetched_schema_ids.schema_ids
            if schema_id
        ]

        if not fetch_schemas:
            raise CloudApiException("Could not publish schema.", 500)
        if len(fetch_schemas) > 1:
            error_message = (
                f"Multiple schemas with name {schema.var_schema.name} "
                f"and version {schema.var_schema.version} exist."
                f"These are: `{fetched_schema_ids.schema_ids!s}`."
            )
            raise CloudApiException(error_message, 409)
        fetched_schema: GetSchemaResult = fetch_schemas[0]

        # Schema exists with different attributes
        if set(fetched_schema.var_schema.attr_names) != set(
            schema.var_schema.attr_names
        ):
            error_message = (
                "Error creating schema: Schema already exists with different attribute "
                f"names. Given: `{set(schema.var_schema.attr_names)!s}`. "
                f"Found: `{set(fetched_schema.var_schema.attr_names)!s}`."
            )
            raise CloudApiException(error_message, 409)

        result = anoncreds_credential_schema(fetched_schema)
        self._logger.debug(
            "Schema already exists on ledger. Returning schema definition: `{}`.",
            result,
        )
        return result

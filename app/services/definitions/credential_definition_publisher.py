import asyncio
from logging import Logger

from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException, handle_acapy_call
from app.services.revocation_registry import wait_for_active_registry
from app.util.check_endorser_connection import check_endorser_connection
from shared import REGISTRY_CREATION_TIMEOUT


class CredentialDefinitionPublisher:
    def __init__(self, controller: AcaPyClient, logger: Logger):
        self._logger = logger
        self._controller = controller

    async def check_endorser_connection(self):
        has_connections = await check_endorser_connection(
            aries_controller=self._controller
        )

        if not has_connections:
            self._logger.error(
                "Failed to create credential definition supporting revocation: "
                "no endorser connection found. Issuer attempted to create a credential "
                "definition with support for revocation but does not have an active "
                "connection with an endorser, which is required for this operation."
            )
            raise CloudApiException(
                "Credential definition creation failed: An active endorser connection "
                "is required to support revocation. Please establish a connection with "
                "an endorser and try again."
            )

    async def publish_credential_definition(self, request_body):
        try:
            result = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.credential_definition.publish_cred_def,
                body=request_body,
            )
        except CloudApiException as e:
            self._logger.warning(
                "An Exception was caught while publishing indy cred def: `{}` `{}`",
                e.detail,
                e.status_code,
            )
            if "already exists" in e.detail:
                self._logger.info("Indy credential definition already exists")
                raise CloudApiException(status_code=409, detail=e.detail) from e
            else:
                self._logger.error(
                    "Error while creating indy credential definition: `{}`", e.detail
                )
                raise CloudApiException(
                    detail=f"Error while creating credential definition: {e.detail}",
                    status_code=e.status_code,
                ) from e

        return result

    async def publish_anoncreds_credential_definition(self, request_body):
        try:
            result = await handle_acapy_call(
                logger=self._logger,
                acapy_call=self._controller.anoncreds_credential_definitions.create_credential_definition,
                body=request_body,
            )
        except CloudApiException as e:
            self._logger.warning(
                "An Exception was caught while publishing anoncreds cred def: `{}` `{}`",
                e.detail,
                e.status_code,
            )
            if "already exists" in e.detail:
                self._logger.info("AnonCreds credential definition already exists")
                raise CloudApiException(status_code=409, detail=e.detail) from e
            else:
                self._logger.error(
                    "Error while creating anoncreds credential definition: `{}`",
                    e.detail,
                )
                raise CloudApiException(
                    detail=f"Error while creating anoncreds credential definition: {e.detail}",
                    status_code=e.status_code,
                ) from e

        return result

    async def wait_for_revocation_registry(self, credential_definition_id, wallet_type):
        try:
            self._logger.debug("Waiting for revocation registry creation")
            await asyncio.wait_for(
                wait_for_active_registry(
                    self._controller, credential_definition_id, wallet_type
                ),
                timeout=REGISTRY_CREATION_TIMEOUT,
            )
        except asyncio.TimeoutError as e:
            self._logger.error("Timeout waiting for revocation registry creation.")
            raise CloudApiException(
                "Timeout waiting for revocation registry creation.",
                504,
            ) from e

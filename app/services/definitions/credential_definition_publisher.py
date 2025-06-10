import asyncio
from logging import Logger

from aries_cloudcontroller import AcaPyClient

from app.exceptions import CloudApiException, handle_acapy_call
from app.services.revocation_registry import wait_for_active_registry
from shared.constants import REGISTRY_CREATION_TIMEOUT


class CredentialDefinitionPublisher:
    def __init__(self, controller: AcaPyClient, logger: Logger):
        self._logger = logger
        self._controller = controller

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

    async def wait_for_revocation_registry(self, credential_definition_id):
        try:
            self._logger.debug("Waiting for revocation registry creation")
            await asyncio.wait_for(
                wait_for_active_registry(self._controller, credential_definition_id),
                timeout=REGISTRY_CREATION_TIMEOUT,
            )
        except TimeoutError as e:
            self._logger.error("Timeout waiting for revocation registry creation.")
            raise CloudApiException(
                "Timeout waiting for revocation registry creation.",
                504,
            ) from e

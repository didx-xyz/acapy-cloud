from logging import Logger
from typing import Dict, List, Optional

from aries_cloudcontroller import (
    AcaPyClient,
    V20CredAttrSpec,
    V20CredExFree,
    V20CredExRecord,
    V20CredFilter,
    V20CredFilterAnoncreds,
    V20CredFilterIndy,
    V20CredOfferConnFreeRequest,
    V20CredPreview,
    V20CredRequestRequest,
    V20CredStoreRequest,
)

from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.issuer import CredentialBase, CredentialType, CredentialWithConnection
from app.services.issuer.acapy_issuer import Issuer
from app.util.credentials import cred_ex_id_no_version
from shared.log_config import get_logger
from shared.models.credential_exchange import (
    CredentialExchange,
    credential_record_to_model_v2,
)

logger = get_logger(__name__)


class IssuerV2(Issuer):
    @classmethod
    async def send_credential(
        cls, controller: AcaPyClient, credential: CredentialWithConnection
    ) -> CredentialExchange:
        bound_logger = logger.bind(
            body={
                # Do not log credential attributes:
                "connection_id": credential.connection_id,
                "credential_type": credential.type,
            }
        )

        credential_preview, cred_filter = cls._get_credential_preview_and_filter(
            credential, bound_logger
        )

        bound_logger.debug("Issue v2 credential (automated)")
        request_body = V20CredExFree(
            auto_remove=credential.auto_remove,
            connection_id=credential.connection_id,
            filter=cred_filter,
            credential_preview=credential_preview,
        )
        record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.issue_credential_automated,
            body=request_body,
        )

        bound_logger.debug("Returning v2 credential result as CredentialExchange.")
        return cls.__record_to_model(record)

    @classmethod
    async def create_offer(
        cls, controller: AcaPyClient, credential: CredentialBase
    ) -> CredentialExchange:
        bound_logger = logger.bind(
            body={
                # Do not log credential attributes:
                "credential_type": credential.type,
            }
        )

        credential_preview, cred_filter = cls._get_credential_preview_and_filter(
            credential, bound_logger
        )

        bound_logger.debug("Creating v2 credential offer")
        request_body = V20CredOfferConnFreeRequest(
            auto_remove=credential.auto_remove,
            credential_preview=credential_preview,
            filter=cred_filter,
        )
        record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.create_offer,
            body=request_body,
        )

        bound_logger.debug("Returning v2 create offer result as CredentialExchange.")
        return cls.__record_to_model(record)

    @classmethod
    def _get_credential_preview_and_filter(
        cls, credential: CredentialBase, bound_logger: Logger
    ):
        credential_preview = None
        if credential.type == CredentialType.INDY:
            bound_logger.debug("Getting credential preview from attributes")
            credential_preview = cls.__preview_from_attributes(
                attributes=credential.indy_credential_detail.attributes
            )
            indy_model = handle_model_with_validation(
                logger=bound_logger,
                model_class=V20CredFilterIndy,
                cred_def_id=credential.indy_credential_detail.credential_definition_id,
            )
            cred_filter = V20CredFilter(indy=indy_model)

        elif credential.type == CredentialType.LD_PROOF:
            cred_filter = V20CredFilter(ld_proof=credential.ld_credential_detail)

        elif credential.type == CredentialType.ANONCREDS:
            bound_logger.debug("Getting credential preview from attributes")
            credential_preview = cls.__preview_from_attributes(
                attributes=credential.anoncreds_credential_detail.attributes
            )
            anon_model = handle_model_with_validation(
                logger=bound_logger,
                model_class=V20CredFilterAnoncreds,
                cred_def_id=credential.anoncreds_credential_detail.credential_definition_id,
                issuer_id=credential.anoncreds_credential_detail.issuer_did,
            )
            cred_filter = V20CredFilter(anoncreds=anon_model)

        else:
            raise CloudApiException(
                f"Unsupported credential type: {credential.type.value}", status_code=501
            )

        return credential_preview, cred_filter

    @classmethod
    async def request_credential(
        cls,
        controller: AcaPyClient,
        credential_exchange_id: str,
        auto_remove: Optional[bool] = None,
    ) -> CredentialExchange:
        bound_logger = logger.bind(
            body={"credential_exchange_id": credential_exchange_id}
        )
        credential_exchange_id = cred_ex_id_no_version(credential_exchange_id)

        bound_logger.debug("Sending v2 credential request")
        request_body = V20CredRequestRequest(auto_remove=auto_remove)
        record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.send_request,
            cred_ex_id=credential_exchange_id,
            body=request_body,
        )

        bound_logger.debug("Returning v2 send request result as CredentialExchange.")
        return cls.__record_to_model(record)

    @classmethod
    async def store_credential(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> CredentialExchange:
        bound_logger = logger.bind(
            body={"credential_exchange_id": credential_exchange_id}
        )
        credential_exchange_id = cred_ex_id_no_version(credential_exchange_id)

        bound_logger.debug("Storing v2 credential record")
        request_body = V20CredStoreRequest()
        record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.store_credential,
            cred_ex_id=credential_exchange_id,
            body=request_body,
        )

        if not record.cred_ex_record:
            bound_logger.error("Stored record has no credential exchange record.")
            raise CloudApiException("Stored record has no credential exchange record.")

        bound_logger.debug(
            "Returning v2 store credential result as CredentialExchange."
        )
        return cls.__record_to_model(record.cred_ex_record)

    @classmethod
    async def delete_credential_exchange_record(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> None:
        bound_logger = logger.bind(
            body={"credential_exchange_id": credential_exchange_id}
        )
        credential_exchange_id = cred_ex_id_no_version(credential_exchange_id)

        bound_logger.debug("Deleting v2 credential record")
        await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.delete_record,
            cred_ex_id=credential_exchange_id,
        )
        bound_logger.debug("Successfully deleted credential record.")

    @classmethod
    async def get_records(
        cls,
        controller: AcaPyClient,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = "id",
        descending: bool = True,
        connection_id: Optional[str] = None,
        role: Optional[str] = None,
        state: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> List[CredentialExchange]:
        bound_logger = logger.bind(body={"connection_id": connection_id})
        bound_logger.debug("Getting v2 credential records by connection id")
        result = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.get_records,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
            connection_id=connection_id,
            role=role,
            state=state,
            thread_id=thread_id,
        )

        if not result.results:
            bound_logger.debug("No v2 record results.")
            return []

        bound_logger.debug("Returning v2 record results as CredentialExchange.")
        return [
            cls.__record_to_model(record.cred_ex_record)
            for record in result.results
            if record.cred_ex_record
        ]

    @classmethod
    async def get_record(
        cls, controller: AcaPyClient, credential_exchange_id: str
    ) -> CredentialExchange:
        bound_logger = logger.bind(
            body={"credential_exchange_id": credential_exchange_id}
        )
        credential_exchange_id = cred_ex_id_no_version(credential_exchange_id)

        bound_logger.debug("Getting v2 credential record")
        record = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=controller.issue_credential_v2_0.get_record,
            cred_ex_id=credential_exchange_id,
        )

        if not record.cred_ex_record:
            bound_logger.error("Record has no credential exchange record.")
            raise CloudApiException("Record has no credential exchange record.")

        bound_logger.debug("Returning v2 credential record as CredentialExchange.")
        return cls.__record_to_model(record.cred_ex_record)

    @classmethod
    def __record_to_model(cls, record: V20CredExRecord) -> CredentialExchange:
        return credential_record_to_model_v2(record=record)

    @classmethod
    def __preview_from_attributes(
        cls,
        attributes: Dict[str, str],
    ) -> V20CredPreview:
        return V20CredPreview(
            attributes=[
                V20CredAttrSpec(name=name, value=value)
                for name, value in attributes.items()
            ]
        )

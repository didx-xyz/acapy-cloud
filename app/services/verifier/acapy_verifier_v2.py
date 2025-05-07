from typing import List, Optional

from aries_cloudcontroller import (
    AcaPyClient,
    IndyCredPrecis,
    V20PresCreateRequestRequest,
    V20PresProblemReportRequest,
    V20PresRequestByFormat,
    V20PresSendRequestRequest,
    V20PresSpecByFormatRequest,
)

from app.exceptions import CloudApiException, handle_acapy_call
from app.models.verifier import (
    AcceptProofRequest,
    CreateProofRequest,
    RejectProofRequest,
    SendProofRequest,
)
from app.services.verifier.acapy_verifier import Verifier
from shared.log_config import get_logger
from shared.models.presentation_exchange import (
    PresentationExchange,
)
from shared.models.presentation_exchange import (
    presentation_record_to_model as record_to_model,
)
from shared.models.protocol import pres_id_no_version

logger = get_logger(__name__)


class VerifierV2(Verifier):
    @classmethod
    async def create_proof_request(
        cls,
        controller: AcaPyClient,
        create_proof_request: CreateProofRequest,
    ) -> PresentationExchange:
        proof_type = create_proof_request.get_proof_type()
        if proof_type == "anoncreds":
            presentation_request = V20PresRequestByFormat(
                anoncreds=create_proof_request.anoncreds_proof_request
            )
        elif proof_type == "dif":
            presentation_request = V20PresRequestByFormat(
                dif=create_proof_request.dif_proof_request
            )
        else:
            raise CloudApiException(
                "Unsupported credential request. One of anoncreds_proof_request or dif_proof_request must be populated.",
                status_code=501,
            )

        bound_logger = logger.bind(body=create_proof_request)
        bound_logger.debug("Creating v2 proof request")
        request_body = V20PresCreateRequestRequest(
            auto_remove=create_proof_request.auto_remove,
            presentation_request=presentation_request,
            auto_verify=True,
            comment=create_proof_request.comment,
        )
        bound_logger.debug("Sending create request: {}", request_body)
        try:
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.create_proof_request,
                body=request_body,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to create presentation request: {e.detail}", e.status_code
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully created v2 presentation request.")
        return result

    @classmethod
    async def send_proof_request(
        cls,
        controller: AcaPyClient,
        send_proof_request: SendProofRequest,
    ) -> PresentationExchange:
        proof_type = send_proof_request.get_proof_type()
        if proof_type == "anoncreds":
            presentation_request = V20PresRequestByFormat(
                anoncreds=send_proof_request.anoncreds_proof_request
            )
        elif proof_type == "dif":
            presentation_request = V20PresRequestByFormat(
                dif=send_proof_request.dif_proof_request
            )
        else:
            raise CloudApiException(
                "Unsupported credential request. One of anoncreds_proof_request or dif_proof_request must be populated.",
                status_code=501,
            )

        bound_logger = logger.bind(body=send_proof_request)
        request_body = V20PresSendRequestRequest(
            auto_remove=send_proof_request.auto_remove,
            connection_id=send_proof_request.connection_id,
            presentation_request=presentation_request,
            auto_verify=True,
            comment=send_proof_request.comment,
        )
        bound_logger.debug("Sending request: {}", request_body)
        try:
            bound_logger.debug("Send free v2 presentation request")
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.send_request_free,
                body=request_body,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to send presentation request: {e.detail}", e.status_code
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully sent v2 presentation request.")
        return result

    @classmethod
    async def accept_proof_request(
        cls, controller: AcaPyClient, accept_proof_request: AcceptProofRequest
    ) -> PresentationExchange:
        auto_remove = accept_proof_request.auto_remove
        proof_type = accept_proof_request.get_proof_type()
        if proof_type == "anoncreds":
            presentation_spec = V20PresSpecByFormatRequest(
                auto_remove=auto_remove,
                anoncreds=accept_proof_request.anoncreds_presentation_spec,
            )
        elif proof_type == "dif":
            presentation_spec = V20PresSpecByFormatRequest(
                auto_remove=auto_remove, dif=accept_proof_request.dif_presentation_spec
            )
        else:
            raise CloudApiException(
                "Unsupported credential. One of anoncreds_presentation_spec or dif_presentation_spec must be populated.",
                status_code=501,
            )

        bound_logger = logger.bind(body=accept_proof_request)
        pres_ex_id = pres_id_no_version(proof_id=accept_proof_request.proof_id)

        try:
            bound_logger.debug("Send v2 proof presentation")
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.send_presentation,
                pres_ex_id=pres_ex_id,
                body=presentation_spec,
            )

        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to send proof presentation: {e.detail}", e.status_code
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully accepted v2 presentation request.")
        return result

    @classmethod
    async def reject_proof_request(
        cls, controller: AcaPyClient, reject_proof_request: RejectProofRequest
    ) -> None:
        bound_logger = logger.bind(body=reject_proof_request)
        bound_logger.debug("Request to reject v2 presentation exchange record")
        pres_ex_id = pres_id_no_version(proof_id=reject_proof_request.proof_id)

        request_body = V20PresProblemReportRequest(
            description=reject_proof_request.problem_report
        )
        try:
            bound_logger.debug("Submitting v2 problem report")
            await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.report_problem,
                pres_ex_id=pres_ex_id,
                body=request_body,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to send problem report: {e.detail}", e.status_code
            ) from e

        if reject_proof_request.delete_proof_record:
            try:
                bound_logger.debug("Deleting v2 presentation exchange record")
                await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=controller.present_proof_v2_0.delete_record,
                    pres_ex_id=pres_ex_id,
                )
            except CloudApiException as e:
                raise CloudApiException(
                    f"Failed to delete record: {e.detail}", e.status_code
                ) from e

        bound_logger.debug("Successfully rejected v2 presentation exchange record.")

    @classmethod
    async def get_proof_records(
        cls,
        controller: AcaPyClient,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = "id",
        descending: bool = True,
        connection_id: str = None,
        role: str = None,
        state: str = None,
        thread_id: str = None,
    ) -> List[PresentationExchange]:
        try:
            logger.debug("Fetching v2 present-proof exchange records")
            presentation_exchange = await handle_acapy_call(
                logger=logger,
                acapy_call=controller.present_proof_v2_0.get_records,
                limit=limit,
                offset=offset,
                order_by=order_by,
                descending=descending,
                connection_id=connection_id,
                role=role,
                state=state,
                thread_id=thread_id,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to get proof records: {e.detail}", e.status_code
            ) from e

        result = [record_to_model(rec) for rec in presentation_exchange.results or []]
        logger.debug("Successfully got v2 present-proof records.")
        return result

    @classmethod
    async def get_proof_record(
        cls, controller: AcaPyClient, proof_id: str
    ) -> PresentationExchange:
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id)

        try:
            bound_logger.debug("Fetching single v2 present-proof exchange record")
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.get_record,
                pres_ex_id=pres_ex_id,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to get proof record with proof id `{proof_id}`: {e.detail}",
                e.status_code,
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully got v2 present-proof record.")
        return result

    @classmethod
    async def delete_proof(cls, controller: AcaPyClient, proof_id: str) -> None:
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id=proof_id)

        try:
            bound_logger.debug("Deleting v2 present-proof exchange record")
            await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.delete_record,
                pres_ex_id=pres_ex_id,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to delete record with proof id `{proof_id}`: {e.detail}",
                e.status_code,
            ) from e

        bound_logger.debug("Successfully deleted v2 present-proof record.")

    @classmethod
    async def get_credentials_by_proof_id(
        cls,
        controller: AcaPyClient,
        proof_id: str,
        referent: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[IndyCredPrecis]:
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id=proof_id)

        try:
            bound_logger.debug("Getting v2 matching credentials from proof id")
            result = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.get_matching_credentials,
                pres_ex_id=pres_ex_id,
                referent=referent,
                limit=limit,
                offset=offset,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to get credentials with proof id `{proof_id}`: {e.detail}",
                e.status_code,
            ) from e

        if result:
            bound_logger.debug("Successfully got matching v2 credentials.")
        else:
            bound_logger.debug("No matching v2 credentials obtained.")
        return result

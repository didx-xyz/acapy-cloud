from typing import List

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
    ProofRequestType,
    RejectProofRequest,
    SendProofRequest,
)
from app.services.verifier.acapy_verifier import Verifier
from shared.log_config import get_logger
from shared.models.presentation_exchange import PresentationExchange
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
        if create_proof_request.type == ProofRequestType.INDY:
            presentation_request = V20PresRequestByFormat(
                indy=create_proof_request.indy_proof_request
            )
        elif create_proof_request.type == ProofRequestType.LD_PROOF:
            presentation_request = V20PresRequestByFormat(
                dif=create_proof_request.dif_proof_request
            )
        else:
            raise CloudApiException(
                f"Unsupported credential type: {create_proof_request.type.value}",
                status_code=501,
            )

        bound_logger = logger.bind(body=create_proof_request)
        bound_logger.debug("Creating v2 proof request")
        request_body = V20PresCreateRequestRequest(
            auto_remove=not create_proof_request.save_exchange_record,
            presentation_request=presentation_request,
            auto_verify=True,
            comment=create_proof_request.comment,
            trace=create_proof_request.trace,
        )
        try:
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.create_proof_request,
                body=request_body,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to create presentation request: {e.detail}.", e.status_code
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
        if send_proof_request.type == ProofRequestType.INDY:
            presentation_request = V20PresRequestByFormat(
                indy=send_proof_request.indy_proof_request
            )
        elif send_proof_request.type == ProofRequestType.LD_PROOF:
            presentation_request = V20PresRequestByFormat(
                dif=send_proof_request.dif_proof_request
            )
        else:
            raise CloudApiException(
                f"Unsupported credential type: {send_proof_request.type.value}",
                status_code=501,
            )

        bound_logger = logger.bind(body=send_proof_request)
        request_body = V20PresSendRequestRequest(
            auto_remove=not send_proof_request.save_exchange_record,
            connection_id=send_proof_request.connection_id,
            presentation_request=presentation_request,
            auto_verify=True,
            comment=send_proof_request.comment,
            trace=send_proof_request.trace,
        )
        try:
            bound_logger.debug("Send free v2 presentation request")
            presentation_exchange = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.send_request_free,
                body=request_body,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to send presentation request: {e.detail}.", e.status_code
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully created v2 presentation request.")
        return result

    @classmethod
    async def accept_proof_request(
        cls, controller: AcaPyClient, accept_proof_request: AcceptProofRequest
    ) -> PresentationExchange:
        auto_remove = not accept_proof_request.save_exchange_record
        if accept_proof_request.type == ProofRequestType.INDY:
            presentation_spec = V20PresSpecByFormatRequest(
                auto_remove=auto_remove,
                indy=accept_proof_request.indy_presentation_spec,
            )
        elif accept_proof_request.type == ProofRequestType.LD_PROOF:
            presentation_spec = V20PresSpecByFormatRequest(
                auto_remove=auto_remove, dif=accept_proof_request.dif_presentation_spec
            )
        else:
            raise CloudApiException(
                f"Unsupported credential type: {accept_proof_request.type.value}",
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
                f"Failed to send proof presentation: {e.detail}.", e.status_code
            ) from e

        result = record_to_model(presentation_exchange)
        bound_logger.debug("Successfully created v2 presentation request.")
        return result

    @classmethod
    async def reject_proof_request(
        cls, controller: AcaPyClient, reject_proof_request: RejectProofRequest
    ) -> None:
        bound_logger = logger.bind(body=reject_proof_request)
        bound_logger.info("Request to reject v2 presentation exchange record")
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
                f"Failed to send problem report: {e.detail}.", e.status_code
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
                    f"Failed to delete record: {e.detail}.", e.status_code
                ) from e

        bound_logger.info("Successfully rejected v2 presentation exchange record.")

    @classmethod
    async def get_proof_records(
        cls,
        controller: AcaPyClient,
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
                connection_id=connection_id,
                role=role,
                state=state,
                thread_id=thread_id,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to get proof records: {e.detail}.", e.status_code
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
                f"Failed to get proof record with proof id `{proof_id}`: {e.detail}.",
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
                f"Failed to delete record with proof id `{proof_id}`: {e.detail}.",
                e.status_code,
            ) from e

        bound_logger.debug("Successfully deleted v2 present-proof record.")

    @classmethod
    async def get_credentials_by_proof_id(
        cls, controller: AcaPyClient, proof_id: str
    ) -> List[IndyCredPrecis]:
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id=proof_id)

        try:
            bound_logger.debug("Getting v2 matching credentials from proof id")
            result = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=controller.present_proof_v2_0.get_matching_credentials,
                pres_ex_id=pres_ex_id,
            )
        except CloudApiException as e:
            raise CloudApiException(
                f"Failed to get credentials with proof id `{proof_id}`: {e.detail}.",
                e.status_code,
            ) from e

        if result:
            bound_logger.debug("Successfully got matching v2 credentials.")
        else:
            bound_logger.debug("No matching v2 credentials obtained.")
        return result

from aries_cloudcontroller import (
    AcaPyClient,
    V20PresCreateRequestRequest,
    V20PresProblemReportRequest,
    V20PresRequestByFormat,
    V20PresSendRequestRequest,
    V20PresSpecByFormatRequest,
)

from app.exceptions import CloudApiException
from app.models.verifier import (
    AcceptProofRequest,
    CreateProofRequest,
    ProofRequestType,
    RejectProofRequest,
    SendProofRequest,
)
from app.services.verifier.acapy_verifier import Verifier
from shared.log_config import get_logger
from shared.models.conversion import presentation_record_to_model as record_to_model
from shared.models.protocol import pres_id_no_version
from shared.models.webhook_topics import PresentationExchange

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
                f"Unsupported credential type: {create_proof_request.type}",
                status_code=501,
            )

        bound_logger = logger.bind(body=create_proof_request)
        bound_logger.debug("Creating v2 proof request")
        auto_remove = not create_proof_request.save_exchange_record
        try:
            proof_record = await controller.present_proof_v2_0.create_proof_request(
                body=V20PresCreateRequestRequest(
                    auto_remove=auto_remove,
                    presentation_request=presentation_request,
                    auto_verify=create_proof_request.auto_verify,
                    comment=create_proof_request.comment,
                    trace=create_proof_request.trace,
                )
            )
            bound_logger.debug("Returning v2 PresentationExchange.")
            return record_to_model(proof_record)
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while creating presentation request."
            )
            raise CloudApiException("Failed to create presentation request.") from e

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
                f"Unsupported credential type: {send_proof_request.type}",
                status_code=501,
            )

        bound_logger = logger.bind(body=send_proof_request)
        auto_remove = not send_proof_request.save_exchange_record
        try:
            bound_logger.debug("Send free v2 presentation request")
            presentation_exchange = (
                await controller.present_proof_v2_0.send_request_free(
                    body=V20PresSendRequestRequest(
                        auto_remove=auto_remove,
                        connection_id=send_proof_request.connection_id,
                        presentation_request=presentation_request,
                        auto_verify=send_proof_request.auto_verify,
                        comment=send_proof_request.comment,
                        trace=send_proof_request.trace,
                    )
                )
            )
            result = record_to_model(presentation_exchange)
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while sending presentation request."
            )
            raise CloudApiException("Failed to send presentation request.") from e

        if result:
            bound_logger.debug("Successfully sent v2 presentation request.")
        else:
            bound_logger.warning("No result from sending v2 presentation request.")
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
                f"Unsupported credential type: {accept_proof_request.type}",
                status_code=501,
            )

        bound_logger = logger.bind(body=accept_proof_request)
        pres_ex_id = pres_id_no_version(proof_id=accept_proof_request.proof_id)

        try:
            bound_logger.debug("Send v2 proof presentation")
            presentation_record = await controller.present_proof_v2_0.send_presentation(
                pres_ex_id=pres_ex_id, body=presentation_spec
            )
            result = record_to_model(presentation_record)
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while sending a proof presentation."
            )
            raise CloudApiException("Failed to send proof presentation.") from e

        if result:
            bound_logger.debug("Successfully sent v2 proof presentation.")
        else:
            bound_logger.warning("No result from sending v2 proof presentation.")
        return result

    @classmethod
    async def reject_proof_request(
        cls, controller: AcaPyClient, reject_proof_request: RejectProofRequest
    ) -> None:
        bound_logger = logger.bind(body=reject_proof_request)
        bound_logger.info("Request to reject v2 presentation exchange record")
        pres_ex_id = pres_id_no_version(proof_id=reject_proof_request.proof_id)

        # Report problem if desired
        if reject_proof_request.problem_report:
            try:
                bound_logger.debug("Submitting v2 problem report")
                await controller.present_proof_v2_0.report_problem(
                    pres_ex_id=pres_ex_id,
                    body=V20PresProblemReportRequest(
                        description=reject_proof_request.problem_report
                    ),
                )
            except Exception as e:
                bound_logger.exception(
                    "An unexpected error occurred while reporting problem."
                )
                raise CloudApiException("Failed to report problem.") from e

        try:
            bound_logger.debug("Deleting v2 presentation exchange record")
            await controller.present_proof_v2_0.delete_record(pres_ex_id=pres_ex_id)
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while deleting record."
            )
            raise CloudApiException("Failed to delete record.") from e

        bound_logger.info("Successfully rejected v2 presentation exchange record.")

    @classmethod
    async def get_proof_records(cls, controller: AcaPyClient):
        try:
            logger.debug("Fetching v2 present-proof exchange records")
            presentation_exchange = await controller.present_proof_v2_0.get_records()
            result = [
                record_to_model(rec) for rec in presentation_exchange.results or []
            ]
        except Exception as e:
            logger.exception("An unexpected error occurred while getting records.")
            raise CloudApiException("Failed to get proof records.") from e

        if result:
            logger.debug("Successfully got v2 present-proof records.")
        else:
            logger.info("No v2 present-proof records obtained.")
        return result

    @classmethod
    async def get_proof_record(cls, controller: AcaPyClient, proof_id: str):
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id)

        try:
            bound_logger.debug("Fetching single v2 present-proof exchange record")
            presentation_exchange = await controller.present_proof_v2_0.get_record(
                pres_ex_id=pres_ex_id
            )
            result = record_to_model(presentation_exchange)
        except Exception as e:
            bound_logger.exception("An unexpected error occurred while getting record.")
            raise CloudApiException(
                f"Failed to get proof record with proof id `{proof_id}`."
            ) from e

        if result:
            bound_logger.debug("Successfully got v2 present-proof record.")
        else:
            bound_logger.info("No v2 present-proof record obtained.")
        return result

    @classmethod
    async def delete_proof(cls, controller: AcaPyClient, proof_id: str):
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id=proof_id)

        try:
            bound_logger.debug("Deleting v2 present-proof exchange record")
            await controller.present_proof_v2_0.delete_record(pres_ex_id=pres_ex_id)
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while deleting record."
            )
            raise CloudApiException(
                f"Failed to delete record with proof id `{proof_id}`."
            ) from e

        bound_logger.debug("Successfully deleted v2 present-proof record.")

    @classmethod
    async def get_credentials_by_proof_id(cls, controller: AcaPyClient, proof_id: str):
        bound_logger = logger.bind(body={"proof_id": proof_id})
        pres_ex_id = pres_id_no_version(proof_id=proof_id)

        try:
            bound_logger.debug("Getting v2 matching credentials from proof id")
            result = await controller.present_proof_v2_0.get_matching_credentials(
                pres_ex_id=pres_ex_id
            )
        except Exception as e:
            bound_logger.exception(
                "An unexpected error occurred while getting matching credentials."
            )
            raise CloudApiException(
                f"Failed to get credentials with proof id `{proof_id}`."
            ) from e

        if result:
            bound_logger.debug("Successfully got matching v2 credentials.")
        else:
            bound_logger.debug("No matching v2 credentials obtained.")
        return result

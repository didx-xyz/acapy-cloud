import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    AnonCredsPresSpec,
    ApiException,
    DIFPresSpec,
    IndyCredInfo,
    IndyCredPrecis,
    V20PresExRecordList,
)
from pydantic import ValidationError

from app.exceptions.cloudapi_exception import CloudApiException
from app.models.verifier import (
    AcceptProofRequest,
    CreateProofRequest,
    CredInfo,
    CredPrecis,
    RejectProofRequest,
    SendProofRequest,
)
from app.services.verifier.acapy_verifier_v2 import VerifierV2
from app.tests.services.verifier.utils import (
    dif_proof_request,
    sample_anoncreds_proof_request,
    v20_presentation_exchange_records,
)
from shared.models.presentation_exchange import (
    PresentationExchange,
)
from shared.models.presentation_exchange import (
    presentation_record_to_model as record_to_model,
)


@pytest.mark.anyio
@pytest.mark.parametrize("proof_type", ["ld_proof", "anoncreds"])
async def test_create_proof_request(
    mock_agent_controller: AcaPyClient, proof_type
) -> None:
    present_proof_v2_0 = mock_agent_controller.present_proof_v2_0
    present_proof_v2_0.create_proof_request.return_value = (
        v20_presentation_exchange_records[0]
    )
    create_proof_request = CreateProofRequest(
        dif_proof_request=(dif_proof_request if proof_type == "ld_proof" else None),
        anoncreds_proof_request=(
            sample_anoncreds_proof_request() if proof_type == "anoncreds" else None
        ),
    )

    created_proof_request = await VerifierV2.create_proof_request(
        controller=mock_agent_controller,
        create_proof_request=create_proof_request,
    )
    assert isinstance(created_proof_request, PresentationExchange)


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_create_proof_request_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.create_proof_request.side_effect = (
        ApiException(reason=error_detail, status=status_code)
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to create presentation request: {error_detail}",
    ) as exc:
        await VerifierV2.create_proof_request(
            controller=mock_agent_controller,
            create_proof_request=CreateProofRequest(
                anoncreds_proof_request=sample_anoncreds_proof_request(),
            ),
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize("proof_type", ["ld_proof", "anoncreds"])
async def test_send_proof_request(
    mock_agent_controller: AcaPyClient, proof_type
) -> None:
    mock_agent_controller.present_proof_v2_0.send_request_free.return_value = (
        v20_presentation_exchange_records[0]
    )
    send_proof_request = SendProofRequest(
        dif_proof_request=(dif_proof_request if proof_type == "ld_proof" else None),
        anoncreds_proof_request=(
            sample_anoncreds_proof_request() if proof_type == "anoncreds" else None
        ),
        connection_id="abcde",
    )

    created_proof_send_proposal = await VerifierV2.send_proof_request(
        controller=mock_agent_controller,
        send_proof_request=send_proof_request,
    )

    assert isinstance(created_proof_send_proposal, PresentationExchange)


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_send_proof_request_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    with pytest.raises(ValidationError):
        await VerifierV2.send_proof_request(
            mock_agent_controller,
            send_proof_request=SendProofRequest(anoncreds_proof_request="I am invalid"),
        )

    mock_agent_controller.present_proof_v2_0.send_request_free.side_effect = (
        ApiException(reason=error_detail, status=status_code)
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to send presentation request: {error_detail}",
    ) as exc:
        await VerifierV2.send_proof_request(
            controller=mock_agent_controller,
            send_proof_request=SendProofRequest(
                anoncreds_proof_request=sample_anoncreds_proof_request(),
                connection_id="abc",
            ),
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize("proof_type", ["ld_proof", "anoncreds"])
async def test_accept_proof_request(
    mock_agent_controller: AcaPyClient, proof_type
) -> None:
    mock_agent_controller.present_proof_v2_0.send_presentation.return_value = (
        v20_presentation_exchange_records[0]
    )
    accept_proof_request = AcceptProofRequest(
        dif_presentation_spec=DIFPresSpec() if proof_type == "ld_proof" else None,
        anoncreds_presentation_spec=(
            AnonCredsPresSpec(
                requested_attributes={},
                requested_predicates={},
                self_attested_attributes={},
            )
            if proof_type == "anoncreds"
            else None
        ),
        proof_id="v2-123",
    )

    accepted_proof_request = await VerifierV2.accept_proof_request(
        mock_agent_controller,
        accept_proof_request=accept_proof_request,
    )

    assert isinstance(accepted_proof_request, PresentationExchange)


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_accept_proof_request_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.send_presentation.side_effect = (
        ApiException(reason=error_detail, status=status_code)
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to send proof presentation: {error_detail}",
    ) as exc:
        await VerifierV2.accept_proof_request(
            controller=mock_agent_controller,
            accept_proof_request=AcceptProofRequest(
                proof_id="v2-123",
                anoncreds_presentation_spec=AnonCredsPresSpec(
                    requested_attributes={},
                    requested_predicates={},
                    self_attested_attributes={},
                ),
            ),
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
async def test_reject_proof_reject(mock_agent_controller: AcaPyClient) -> None:
    mock_agent_controller.present_proof_v2_0.delete_record.return_value = {}
    mock_agent_controller.present_proof_v2_0.report_problem.return_value = {}

    deleted_proof_request = await VerifierV2.reject_proof_request(
        controller=mock_agent_controller,
        reject_proof_request=RejectProofRequest(
            proof_id="v2-abc", problem_report="some message", delete_proof_record=True
        ),
    )

    assert deleted_proof_request is None


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_reject_proof_reject_exception_report(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.report_problem.side_effect = ApiException(
        reason=error_detail, status=status_code
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to send problem report: {error_detail}",
    ) as exc:
        await VerifierV2.reject_proof_request(
            controller=mock_agent_controller,
            reject_proof_request=RejectProofRequest(
                proof_id="v2-abc", problem_report="bad"
            ),
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_reject_proof_reject_exception_delete(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.report_problem.return_value = {}
    mock_agent_controller.present_proof_v2_0.delete_record.side_effect = ApiException(
        reason=error_detail, status=status_code
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to delete record: {error_detail}",
    ) as exc:
        await VerifierV2.reject_proof_request(
            controller=mock_agent_controller,
            reject_proof_request=RejectProofRequest(
                proof_id="v2-abc", problem_report="bad", delete_proof_record=True
            ),
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
async def test_get_proof_records(mock_agent_controller: AcaPyClient) -> None:
    mock_agent_controller.present_proof_v2_0.get_records.return_value = (
        V20PresExRecordList(results=v20_presentation_exchange_records)
    )

    proof_records = await VerifierV2.get_proof_records(
        controller=mock_agent_controller,
    )

    expected_result = [
        record_to_model(rec) for rec in v20_presentation_exchange_records
    ]
    assert proof_records == expected_result


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_get_proof_records_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.get_records.side_effect = ApiException(
        reason=error_detail, status=status_code
    )

    with pytest.raises(
        CloudApiException,
        match=f"Failed to get proof records: {error_detail}",
    ) as exc:
        await VerifierV2.get_proof_records(
            controller=mock_agent_controller,
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
async def test_get_proof_record(mock_agent_controller: AcaPyClient) -> None:
    mock_agent_controller.present_proof_v2_0.get_record.return_value = (
        v20_presentation_exchange_records[0]
    )

    proof_record = await VerifierV2.get_proof_record(
        controller=mock_agent_controller, proof_id="v2-abc"
    )

    expected_result = record_to_model(v20_presentation_exchange_records[0])
    assert proof_record == expected_result


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_get_proof_record_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.get_record.side_effect = ApiException(
        reason=error_detail, status=status_code
    )
    proof_id = "v2-abc"
    with pytest.raises(
        CloudApiException,
        match=f"Failed to get proof record with proof id `{proof_id}`: {error_detail}",
    ) as exc:
        await VerifierV2.get_proof_record(
            controller=mock_agent_controller, proof_id=proof_id
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
async def test_delete_proof(mock_agent_controller: AcaPyClient) -> None:
    mock_agent_controller.present_proof_v2_0.delete_record.return_value = None
    result = await VerifierV2.delete_proof(
        controller=mock_agent_controller, proof_id="v2-abc"
    )
    assert result is None


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_delete_proof_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.delete_record.side_effect = ApiException(
        reason=error_detail, status=status_code
    )
    proof_id = "v2-abc"
    with pytest.raises(
        CloudApiException,
        match=f"Failed to delete record with proof id `{proof_id}`: {error_detail}",
    ) as exc:
        await VerifierV2.delete_proof(
            controller=mock_agent_controller, proof_id=proof_id
        )

    assert exc.value.status_code == status_code


@pytest.mark.anyio
@pytest.mark.parametrize("empty_result", [True, False])
async def test_get_credentials_by_proof_id(
    mock_agent_controller: AcaPyClient, empty_result: bool
) -> None:
    mock_agent_controller.present_proof_v2_0.get_matching_credentials.return_value = (
        [] if empty_result else [IndyCredPrecis(cred_info=IndyCredInfo())]
    )

    creds = await VerifierV2.get_credentials_by_proof_id(
        controller=mock_agent_controller, proof_id="v2-abc"
    )

    assert isinstance(creds, list)

    if not empty_result:
        cred = creds[0]
        assert isinstance(cred, CredPrecis)
        assert isinstance(cred.cred_info, CredInfo)


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 500])
@pytest.mark.parametrize("error_detail", ["Error msg", "is dynamic"])
async def test_get_credentials_by_proof_id_exception(
    mock_agent_controller: AcaPyClient, status_code: int, error_detail: str
) -> None:
    mock_agent_controller.present_proof_v2_0.get_matching_credentials.side_effect = (
        ApiException(reason=error_detail, status=status_code)
    )
    proof_id = "v2-abc"
    with pytest.raises(
        CloudApiException,
        match=f"Failed to get credentials with proof id `{proof_id}`: {error_detail}",
    ) as exc:
        await VerifierV2.get_credentials_by_proof_id(
            controller=mock_agent_controller, proof_id=proof_id
        )

    assert exc.value.status_code == status_code

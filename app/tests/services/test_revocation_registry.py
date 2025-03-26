from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    ApiException,
    ClearPendingRevocationsRequest,
    CredRevRecordResult,
    CredRevRecordResultSchemaAnoncreds,
    IssuerCredRevRecord,
    IssuerCredRevRecordSchemaAnoncreds,
    IssuerRevRegRecord,
    PublishRevocations,
    PublishRevocationsOptions,
    PublishRevocationsResultSchemaAnoncreds,
    PublishRevocationsSchemaAnoncreds,
    RevokeRequest,
    RevokeRequestSchemaAnoncreds,
    RevRegResult,
    RevRegResultSchemaAnoncreds,
    RevRegsCreated,
    RevRegsCreatedSchemaAnoncreds,
    TransactionRecord,
    TxnOrPublishRevocationsResult,
    V20CredExRecordDetail,
    V20CredExRecordIndy,
)
from mockito import verify, when

import app.services.revocation_registry as test_module
from app.exceptions import CloudApiException
from app.models.issuer import ClearPendingRevocationsResult, RevokedResponse
from app.tests.util.mock import to_async

cred_def_id = "VagGATdBsVdBeFKeoYPe7H:3:CL:141:5d211963-3478-4de4-b8b6-9072759a71c8"
cred_rev_id = "1234"
cred_ex_id = "c7c909f4-f670-49bd-9d81-53fba6bb23b8"
max_cred_num = 32767
revocation_registry_id = (
    "VagGATdBsVdBeFKeoYPe7H:4:VagGATdBsVdBeFKeoYPe7H:3:CL:141:"
    "QIOPN:CL_ACCUM:5d211963-3478-4de4-b8b6-9072759a71c8"
)
revocation_registry_credential_map_input = {"rev_reg_id1": ["1", "2"]}
revocation_registry_credential_map_output = {"rev_reg_id1": [1, 2]}
conn_id = "12345"
transaction_id = "1234"
message_attach_data = {
    "data": {
        "json": {
            "operation": {
                "revocRegDefId": "rev_reg_id_1",
                "value": {"revoked": [1]},
            },
        }
    }
}
txn_data = {"txn": {"messages_attach": [message_attach_data]}}


@pytest.mark.anyio
async def test_get_active_revocation_registry_for_credential(
    mock_agent_controller: AcaPyClient,
):
    # Success
    when(mock_agent_controller.revocation).get_active_registry_for_cred_def(
        cred_def_id=cred_def_id
    ).thenReturn(
        to_async(
            RevRegResult(
                result=IssuerRevRegRecord(
                    cred_def_id=cred_def_id, max_cred_num=max_cred_num
                )
            )
        )
    )
    active_rev_reg_result = (
        await test_module.get_active_revocation_registry_for_credential(
            controller=mock_agent_controller, credential_definition_id=cred_def_id
        )
    )

    assert isinstance(active_rev_reg_result, IssuerRevRegRecord)
    assert active_rev_reg_result.cred_def_id == cred_def_id
    assert active_rev_reg_result.max_cred_num == max_cred_num

    # Fail
    with pytest.raises(
        CloudApiException, match="Error retrieving revocation registry"
    ) as exc:
        when(mock_agent_controller.revocation).get_active_registry_for_cred_def(
            cred_def_id=cred_def_id
        ).thenReturn(to_async(None))
        await test_module.get_active_revocation_registry_for_credential(
            mock_agent_controller, credential_definition_id=cred_def_id
        )
        assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_revoke_credential(mock_agent_controller: AcaPyClient):
    # Success
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        when(mock_agent_controller.revocation).revoke_credential(
            body=RevokeRequest(cred_ex_id=cred_ex_id, publish=False)
        ).thenReturn(to_async({}))

        revoke_credential_result = await test_module.revoke_credential(
            controller=mock_agent_controller,
            credential_exchange_id=cred_ex_id,
            auto_publish_to_ledger=False,
        )

        assert revoke_credential_result.cred_rev_ids_published == {}

        # Fail
        error_msg = "dummy_message"
        with pytest.raises(
            CloudApiException, match=f"Failed to revoke credential: {error_msg}"
        ) as exc:
            when(mock_agent_controller.revocation).revoke_credential(
                body=RevokeRequest(cred_ex_id=cred_ex_id, publish=False)
            ).thenRaise(ApiException(reason=error_msg, status=500))
            await test_module.revoke_credential(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
                auto_publish_to_ledger=False,
            )
            assert exc.value.status_code == 500

    # Success for askar-anoncreds
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar-anoncreds"
        when(mock_agent_controller.anoncreds_revocation).revoke(
            body=RevokeRequestSchemaAnoncreds(cred_ex_id=cred_ex_id, publish=False)
        ).thenReturn(to_async({}))

        revoke_credential_result = await test_module.revoke_credential(
            controller=mock_agent_controller,
            credential_exchange_id=cred_ex_id,
            auto_publish_to_ledger=False,
        )

        assert revoke_credential_result.cred_rev_ids_published == {}


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_publish_pending_revocations_success(
    mock_agent_controller: AcaPyClient, wallet_type
):
    # Simulate successful validation
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type
        when(test_module).validate_rev_reg_ids(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        ).thenReturn(to_async())

        # Simulate successful publish revocations call
        if wallet_type == "askar":
            when(mock_agent_controller.revocation).publish_revocations(
                body=PublishRevocations(
                    rrid2crid=revocation_registry_credential_map_input
                )
            ).thenReturn(
                to_async(
                    TxnOrPublishRevocationsResult(
                        txn=[
                            TransactionRecord(
                                transaction_id="97a46fab-5499-42b3-a2a1-7eb9faad31c0"
                            )
                        ]
                    )
                )
            )
        elif wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).publish_revocations(
                body=PublishRevocationsSchemaAnoncreds(
                    rrid2crid=revocation_registry_credential_map_input,
                    options=PublishRevocationsOptions(
                        create_transaction_for_endorser=True
                    ),
                )
            ).thenReturn(
                to_async(
                    PublishRevocationsResultSchemaAnoncreds(
                        rrid2crid=revocation_registry_credential_map_output
                    )
                )
            )

        await test_module.publish_pending_revocations(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        )

        if wallet_type == "askar":
            verify(mock_agent_controller.revocation, times=1).publish_revocations(
                body=PublishRevocations(
                    rrid2crid=revocation_registry_credential_map_input
                )
            )
        elif wallet_type == "askar-anoncreds":
            verify(
                mock_agent_controller.anoncreds_revocation, times=1
            ).publish_revocations(
                body=PublishRevocationsSchemaAnoncreds(
                    rrid2crid=revocation_registry_credential_map_input,
                    options=PublishRevocationsOptions(
                        create_transaction_for_endorser=True
                    ),
                )
            )


@pytest.mark.anyio
async def test_publish_pending_revocations_empty_response(
    mock_agent_controller: AcaPyClient,
):
    # Simulate successful validation
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar-anoncreds"
        when(test_module).validate_rev_reg_ids(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        ).thenReturn(to_async())

        # Simulate successful publish revocations call
        when(mock_agent_controller.anoncreds_revocation).publish_revocations(
            body=PublishRevocationsSchemaAnoncreds(
                rrid2crid=revocation_registry_credential_map_input,
                options=PublishRevocationsOptions(create_transaction_for_endorser=True),
            )
        ).thenReturn(
            to_async()
        )  # Return empty response

        result = await test_module.publish_pending_revocations(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        )

        assert result is None  # We still publish, but no result is returned

        verify(mock_agent_controller.anoncreds_revocation, times=1).publish_revocations(
            body=PublishRevocationsSchemaAnoncreds(
                rrid2crid=revocation_registry_credential_map_input,
                options=PublishRevocationsOptions(create_transaction_for_endorser=True),
            )
        )


@pytest.mark.anyio
async def test_publish_pending_revocations_failure(mock_agent_controller: AcaPyClient):
    error_message = "Failed to publish due to network error"
    status_code = 500

    # Simulate successful validation
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        when(test_module).validate_rev_reg_ids(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        ).thenReturn(to_async())

        # Simulate failure in publish revocations call
        when(mock_agent_controller.revocation).publish_revocations(
            body=PublishRevocations(rrid2crid=revocation_registry_credential_map_input)
        ).thenRaise(ApiException(reason=error_message, status=status_code))

        with pytest.raises(
            CloudApiException,
            match=f"Failed to publish pending revocations: {error_message}",
        ) as exc:
            await test_module.publish_pending_revocations(
                controller=mock_agent_controller,
                revocation_registry_credential_map=revocation_registry_credential_map_input,
            )

        assert exc.value.status_code == status_code

        # You may also verify that publish_revocations was attempted
        verify(mock_agent_controller.revocation, times=1).publish_revocations(
            body=PublishRevocations(rrid2crid=revocation_registry_credential_map_input)
        )


@pytest.mark.anyio
async def test_publish_pending_revocations_no_txn_response(
    mock_agent_controller: AcaPyClient,
):

    # Simulate successful validation
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        when(test_module).validate_rev_reg_ids(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        ).thenReturn(to_async())

        # Simulate failure in publish revocations call
        when(mock_agent_controller.revocation).publish_revocations(
            body=PublishRevocations(rrid2crid=revocation_registry_credential_map_input)
        ).thenReturn(to_async(TxnOrPublishRevocationsResult()))

        await test_module.publish_pending_revocations(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        )

        # You may also verify that publish_revocations was attempted
        verify(mock_agent_controller.revocation, times=1).publish_revocations(
            body=PublishRevocations(rrid2crid=revocation_registry_credential_map_input)
        )


@pytest.mark.anyio
async def test_clear_pending_revocations_success(mock_agent_controller: AcaPyClient):
    expected_result_map = {"rev_reg_id1": []}

    # Simulate successful validation
    when(test_module).validate_rev_reg_ids(
        controller=mock_agent_controller,
        revocation_registry_credential_map=revocation_registry_credential_map_input,
    ).thenReturn(to_async(None))

    # Mock clear_pending_revocations call to return successful result
    when(mock_agent_controller.revocation).clear_pending_revocations(
        body=ClearPendingRevocationsRequest(
            purge=revocation_registry_credential_map_input
        )
    ).thenReturn(to_async(PublishRevocations(rrid2crid=expected_result_map)))

    result = await test_module.clear_pending_revocations(
        controller=mock_agent_controller,
        revocation_registry_credential_map=revocation_registry_credential_map_input,
    )

    assert isinstance(result, ClearPendingRevocationsResult)
    assert result.revocation_registry_credential_map == expected_result_map

    # Verify that clear_pending_revocations was called with the expected arguments
    verify(mock_agent_controller.revocation, times=1).clear_pending_revocations(
        body=ClearPendingRevocationsRequest(
            purge=revocation_registry_credential_map_input
        )
    )


@pytest.mark.anyio
async def test_clear_pending_revocations_failure(mock_agent_controller: AcaPyClient):
    error_message = "Failed to clear due to network error"
    status_code = 500

    # Simulate successful validation
    when(test_module).validate_rev_reg_ids(
        controller=mock_agent_controller,
        revocation_registry_credential_map=revocation_registry_credential_map_input,
    ).thenReturn(to_async(None))

    # Simulate failure in clear_pending_revocations call
    when(mock_agent_controller.revocation).clear_pending_revocations(
        body=ClearPendingRevocationsRequest(
            purge=revocation_registry_credential_map_input
        )
    ).thenRaise(ApiException(reason=error_message, status=status_code))

    with pytest.raises(
        CloudApiException,
        match=f"Failed to clear pending revocations: {error_message}",
    ) as exc:
        await test_module.clear_pending_revocations(
            controller=mock_agent_controller,
            revocation_registry_credential_map=revocation_registry_credential_map_input,
        )

    assert exc.value.status_code == status_code

    # Verify that clear_pending_revocations was attempted
    verify(mock_agent_controller.revocation, times=1).clear_pending_revocations(
        body=ClearPendingRevocationsRequest(
            purge=revocation_registry_credential_map_input
        )
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "wallet_type, schema",
    [
        ("askar", IssuerCredRevRecord),
        ("askar-anoncreds", IssuerCredRevRecordSchemaAnoncreds),
    ],
)
async def test_get_credential_revocation_record_success(
    mock_agent_controller: AcaPyClient, wallet_type, schema
):
    expected_result = schema(
        cred_ex_id=cred_ex_id,
        cred_rev_id=cred_rev_id,
        rev_reg_id=revocation_registry_id,
    )
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type

        # Mock successful response from ACA-Py
        if wallet_type == "askar":
            when(mock_agent_controller.revocation).get_revocation_status(
                cred_ex_id=cred_ex_id,
                cred_rev_id=cred_rev_id,
                rev_reg_id=revocation_registry_id,
            ).thenReturn(to_async(CredRevRecordResult(result=expected_result)))

            result = await test_module.get_credential_revocation_record(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
                credential_revocation_id=cred_rev_id,
                revocation_registry_id=revocation_registry_id,
            )
        else:  # wallet_type == "askar-anoncreds"
            when(mock_agent_controller.anoncreds_revocation).get_cred_rev_record(
                cred_ex_id=cred_ex_id,
                cred_rev_id=cred_rev_id,
                rev_reg_id=revocation_registry_id,
            ).thenReturn(
                to_async(CredRevRecordResultSchemaAnoncreds(result=expected_result))
            )

            result = await test_module.get_credential_revocation_record(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
                credential_revocation_id=cred_rev_id,
                revocation_registry_id=revocation_registry_id,
            )
        assert result == expected_result


@pytest.mark.anyio
async def test_get_credential_revocation_record_api_exception(
    mock_agent_controller: AcaPyClient,
):
    error_message = "Failed to get revocation status"
    status_code = 500

    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"

        # Mock ApiException from ACA-Py
        when(mock_agent_controller.revocation).get_revocation_status(
            cred_ex_id=cred_ex_id, cred_rev_id=ANY, rev_reg_id=ANY
        ).thenRaise(ApiException(reason=error_message, status=status_code))

        with pytest.raises(
            CloudApiException, match=f"Failed to get revocation status: {error_message}"
        ) as exc_info:
            await test_module.get_credential_revocation_record(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
            )

        assert exc_info.value.status_code == status_code


@pytest.mark.anyio
async def test_get_credential_revocation_record_invalid_result_type(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock unexpected response type from ACA-Py
        when(mock_agent_controller.revocation).get_revocation_status(
            cred_ex_id=cred_ex_id, cred_rev_id=ANY, rev_reg_id=ANY
        ).thenReturn(to_async("unexpected_type"))

        with pytest.raises(
            CloudApiException,
            match="Error retrieving revocation status for credential exchange ID",
        ):
            await test_module.get_credential_revocation_record(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
            )


@pytest.mark.anyio
async def test_get_credential_definition_id_from_exchange_id(
    mock_agent_controller: AcaPyClient,
):
    # Success v2
    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=cred_ex_id
    ).thenReturn(
        to_async(
            V20CredExRecordDetail(
                indy=V20CredExRecordIndy(rev_reg_id=revocation_registry_id)
            )
        )
    )

    cred_def_id_result = (
        await test_module.get_credential_definition_id_from_exchange_id(
            controller=mock_agent_controller, credential_exchange_id=cred_ex_id
        )
    )

    assert cred_def_id_result
    assert isinstance(cred_def_id_result, str)
    assert cred_def_id_result == cred_def_id

    # Not found
    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=cred_ex_id
    ).thenRaise(CloudApiException(detail=""))

    cred_def_id_result = (
        await test_module.get_credential_definition_id_from_exchange_id(
            controller=mock_agent_controller, credential_exchange_id=cred_ex_id
        )
    )

    assert cred_def_id_result is None

    # KeyError scenario
    when(mock_agent_controller.issue_credential_v2_0).get_record(
        cred_ex_id=cred_ex_id
    ).thenReturn(
        to_async(V20CredExRecordDetail(indy=V20CredExRecordIndy(rev_reg_id=None)))
    )

    cred_def_id_result = (
        await test_module.get_credential_definition_id_from_exchange_id(
            controller=mock_agent_controller, credential_exchange_id=cred_ex_id
        )
    )

    assert cred_def_id_result is None


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_validate_rev_reg_ids_success(
    mock_agent_controller: AcaPyClient, wallet_type
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type
        # Mock successful retrieval of revocation registry
        if wallet_type == "askar":
            when(mock_agent_controller.revocation).get_registry(...).thenReturn(
                to_async(
                    RevRegResult(
                        result=IssuerRevRegRecord(
                            pending_pub=revocation_registry_credential_map_input.get(
                                "rev_reg_id1"
                            )
                        )
                    )
                )
            )
        elif wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).get_revocation_registry(
                rev_reg_id="rev_reg_id1"
            ).thenReturn(
                to_async(
                    RevRegResultSchemaAnoncreds(
                        result=IssuerRevRegRecord(
                            pending_pub=revocation_registry_credential_map_input.get(
                                "rev_reg_id1"
                            )
                        )
                    )
                )
            )
        await test_module.validate_rev_reg_ids(
            mock_agent_controller, revocation_registry_credential_map_input
        )


@pytest.mark.anyio
async def test_validate_rev_reg_ids_non_existent(mock_agent_controller: AcaPyClient):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock ApiException for non-existent revocation registry ID
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id="invalid_rev_reg_id"
        ).thenRaise(ApiException(status=404, reason="Registry ID does not exist"))

        with pytest.raises(
            CloudApiException,
            match="The rev_reg_id `invalid_rev_reg_id` does not exist",
        ) as exc_info:
            await test_module.validate_rev_reg_ids(
                mock_agent_controller, {"invalid_rev_reg_id": ["cred_rev_id_4"]}
            )

        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_validate_rev_reg_ids_error(mock_agent_controller: AcaPyClient):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock ApiException for non-existent revocation registry ID
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id="invalid_rev_reg_id"
        ).thenRaise(ApiException(status=500, reason="ERROR"))

        with pytest.raises(
            CloudApiException,
            match="An error occurred while validating requested",
        ) as exc_info:
            await test_module.validate_rev_reg_ids(
                mock_agent_controller, {"invalid_rev_reg_id": ["cred_rev_id_4"]}
            )

        assert exc_info.value.status_code == 500


@pytest.mark.anyio
async def test_validate_rev_reg_ids_no_pending_publications(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock response with no pending publications
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id="valid_rev_reg_id_1"
        ).thenReturn(
            to_async(RevRegResult(result=IssuerRevRegRecord(pending_pub=None)))
        )

        with pytest.raises(
            CloudApiException, match="No pending publications found"
        ) as exc_info:
            await test_module.validate_rev_reg_ids(
                mock_agent_controller, {"valid_rev_reg_id_1": ["cred_rev_id_1"]}
            )

        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_validate_rev_reg_ids_cred_rev_id_not_pending(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock response where cred_rev_id is not in pending_pub
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id="valid_rev_reg_id_1"
        ).thenReturn(
            to_async(
                RevRegResult(result=IssuerRevRegRecord(pending_pub=["cred_rev_id_2"]))
            )
        )

        with pytest.raises(
            CloudApiException, match="is not pending publication"
        ) as exc_info:
            await test_module.validate_rev_reg_ids(
                mock_agent_controller, {"valid_rev_reg_id_1": ["cred_rev_id_1"]}
            )

        assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_validate_rev_reg_ids_result_none(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock response where cred_rev_id is not in pending_pub
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id="valid_rev_reg_id_1"
        ).thenReturn(to_async(RevRegResult(result=None)))

        with pytest.raises(
            CloudApiException,
            match="Bad request: Failed to retrieve revocation registry",
        ) as exc_info:
            await test_module.validate_rev_reg_ids(
                mock_agent_controller, {"valid_rev_reg_id_1": ["cred_rev_id_1"]}
            )

        assert exc_info.value.status_code == 404


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_get_pending_revocations_success(
    mock_agent_controller: AcaPyClient, wallet_type
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type
        rev_reg_id = "mocked_rev_reg_id"
        # Mock successful response from ACA-Py
        if wallet_type == "askar":
            when(mock_agent_controller.revocation).get_registry(
                rev_reg_id=rev_reg_id
            ).thenReturn(
                to_async(
                    RevRegResult(
                        result=IssuerRevRegRecord(
                            rev_reg_id=rev_reg_id, max_cred_num=max_cred_num
                        )
                    )
                )
            )
        elif wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).get_revocation_registry(
                rev_reg_id=rev_reg_id
            ).thenReturn(
                to_async(
                    RevRegResultSchemaAnoncreds(
                        result=IssuerRevRegRecord(
                            rev_reg_id=rev_reg_id, max_cred_num=max_cred_num
                        )
                    )
                )
            )
        await test_module.get_pending_revocations(
            controller=mock_agent_controller, rev_reg_id=rev_reg_id
        )


@pytest.mark.anyio
async def test_get_pending_revocations_failure(
    mock_agent_controller: AcaPyClient,
):
    error_message = "Failed to get revocation registry"
    status_code = 500

    rev_reg_id = "mocked_rev_reg_id"
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock ApiException from ACA-Py
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id=rev_reg_id
        ).thenRaise(ApiException(reason=error_message, status=status_code))

        with pytest.raises(
            CloudApiException,
            match=f"500: Failed to get pending revocations: {error_message}",
        ) as exc_info:
            await test_module.get_pending_revocations(
                controller=mock_agent_controller, rev_reg_id=rev_reg_id
            )

        assert exc_info.value.status_code == status_code


@pytest.mark.anyio
async def test_get_pending_revocations_result_none(
    mock_agent_controller: AcaPyClient,
):

    rev_reg_id = "mocked_rev_reg_id"
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = "askar"
        # Mock ApiException from ACA-Py
        when(mock_agent_controller.revocation).get_registry(
            rev_reg_id=rev_reg_id
        ).thenReturn(to_async(RevRegResultSchemaAnoncreds(result=None)))

        with pytest.raises(
            CloudApiException,
            match="Error retrieving pending revocations for revocation registry with ID",
        ) as exc_info:
            await test_module.get_pending_revocations(
                controller=mock_agent_controller, rev_reg_id=rev_reg_id
            )

        assert exc_info.value.status_code == 500


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_get_created_active_registries(
    mock_agent_controller: AcaPyClient, wallet_type
):
    active_registries = ["reg_id_1", "reg_id_2"]

    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type

        if wallet_type == "askar":
            when(mock_agent_controller.revocation).get_created_registries(
                cred_def_id=cred_def_id, state="active"
            ).thenReturn(to_async(RevRegsCreated(rev_reg_ids=active_registries)))
        elif wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).get_revocation_registries(
                cred_def_id=cred_def_id, state="finished"
            ).thenReturn(
                to_async(RevRegsCreatedSchemaAnoncreds(rev_reg_ids=active_registries))
            )

        result = await test_module.get_created_active_registries(
            controller=mock_agent_controller,
            cred_def_id=cred_def_id,
            wallet_type=wallet_type,
        )

        assert result == active_registries


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
async def test_get_created_active_registries_error(
    mock_agent_controller: AcaPyClient, wallet_type
):
    with patch(
        "app.services.revocation_registry.get_wallet_type"
    ) as mock_get_wallet_type:
        mock_get_wallet_type.return_value = wallet_type

        if wallet_type == "askar":
            when(mock_agent_controller.revocation).get_created_registries(
                cred_def_id=cred_def_id, state="active"
            ).thenRaise(ApiException(reason="Error", status=500))
        elif wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).get_revocation_registries(
                cred_def_id=cred_def_id, state="finished"
            ).thenRaise(ApiException(reason="Error", status=500))

        with pytest.raises(
            CloudApiException,
            match="Error while creating credential definition",
        ) as exc_info:
            await test_module.get_created_active_registries(
                controller=mock_agent_controller,
                cred_def_id=cred_def_id,
                wallet_type=wallet_type,
            )

        assert exc_info.value.status_code == 500


@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
@pytest.mark.anyio
async def test_revoke_credential_auto_publish_success(
    mock_agent_controller: AcaPyClient, wallet_type
):
    # Mock the get_wallet_type function
    with patch(
        "app.services.revocation_registry.get_wallet_type", return_value=wallet_type
    ):
        # Mock the revocation call
        if wallet_type == "askar-anoncreds":
            when(mock_agent_controller.anoncreds_revocation).revoke(
                body=ANY
            ).thenReturn(to_async({"txn": {"messages_attach": [message_attach_data]}}))

            # Mock the get_revocation_status call to return "revoked"
            when(mock_agent_controller.anoncreds_revocation).get_cred_rev_record(
                ANY
            ).thenReturn(
                to_async(
                    MagicMock(
                        result=MagicMock(
                            state="revoked", rev_reg_id="rev_reg_id_1", cred_rev_id="1"
                        )
                    )
                )
            )

        else:  # wallet_type == "askar"
            when(mock_agent_controller.revocation).revoke_credential(
                body=ANY
            ).thenReturn(to_async({"txn": {"messages_attach": [message_attach_data]}}))

            # Mock the get_revocation_status call to return "revoked"
            when(mock_agent_controller.revocation).get_revocation_status(
                ANY
            ).thenReturn(to_async(MagicMock(result=MagicMock(state="revoked"))))

        response = await test_module.revoke_credential(
            controller=mock_agent_controller,
            credential_exchange_id=cred_ex_id,
            auto_publish_to_ledger=True,
        )

        assert isinstance(response, RevokedResponse)
        assert response.cred_rev_ids_published == {"rev_reg_id_1": [1]}


@pytest.mark.parametrize("wallet_type", ["askar", "askar-anoncreds"])
@pytest.mark.anyio
async def test_revoke_credential_auto_publish_timeout(
    mock_agent_controller: AcaPyClient, wallet_type
):
    with patch(
        "app.services.revocation_registry.get_wallet_type", return_value=wallet_type
    ):
        if wallet_type == "askar-anoncreds":
            mock_agent_controller.anoncreds_revocation.revoke = AsyncMock()
            mock_agent_controller.anoncreds_revocation.get_cred_rev_record = AsyncMock(
                return_value=MagicMock(result=MagicMock(state="not-revoked"))
            )
        else:  # wallet_type == "askar"
            mock_agent_controller.revocation.revoke_credential = AsyncMock()
            mock_agent_controller.revocation.get_revocation_status = AsyncMock(
                return_value=MagicMock(result=MagicMock(state="not-revoked"))
            )

        with patch("app.services.revocation_registry.asyncio.sleep") as mock_sleep:
            mock_sleep.return_value = None

            with pytest.raises(
                CloudApiException,
                match="Could not assert that revocation was published within timeout",
            ):
                await test_module.revoke_credential(
                    controller=mock_agent_controller,
                    credential_exchange_id=cred_ex_id,
                    auto_publish_to_ledger=True,
                )

    if wallet_type == "askar-anoncreds":
        mock_agent_controller.anoncreds_revocation.revoke.assert_called_once()
        assert (
            mock_agent_controller.anoncreds_revocation.get_cred_rev_record.call_count
            == 5
        )
    else:
        mock_agent_controller.revocation.revoke_credential.assert_called_once()
        assert mock_agent_controller.revocation.get_revocation_status.call_count == 5

    assert mock_sleep.call_count == 4


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["askar"])
async def test_revoke_credential_no_result_returned(
    mock_agent_controller: AcaPyClient, wallet_type
):
    with patch(
        "app.services.revocation_registry.get_wallet_type", return_value=wallet_type
    ):
        when(mock_agent_controller.revocation).revoke_credential(body=ANY).thenReturn(
            to_async(None)
        )
        when(mock_agent_controller.revocation).get_revocation_status(ANY).thenReturn(
            to_async(MagicMock(result=MagicMock(state="revoked")))
        )

        with pytest.raises(
            CloudApiException,
            match="Revocation was published but no result was returned",
        ):
            await test_module.revoke_credential(
                controller=mock_agent_controller,
                credential_exchange_id=cred_ex_id,
                auto_publish_to_ledger=True,
            )


@pytest.mark.anyio
async def test_revoke_credential_with_transaction_result(
    mock_agent_controller: AcaPyClient,
):
    with patch(
        "app.services.revocation_registry.get_wallet_type", return_value="askar"
    ):
        # Craft the test data to match the expected structure

        when(mock_agent_controller.revocation).revoke_credential(body=ANY).thenReturn(
            to_async(txn_data)
        )

        when(mock_agent_controller.revocation).get_revocation_status(ANY).thenReturn(
            to_async(MagicMock(result=MagicMock(state="revoked")))
        )
        response = await test_module.revoke_credential(
            controller=mock_agent_controller,
            credential_exchange_id=cred_ex_id,
            auto_publish_to_ledger=True,
        )

        assert isinstance(response, RevokedResponse)
        assert response.cred_rev_ids_published == {
            "rev_reg_id_1": [1]
        }, "The cred_rev_ids_published should match the expected transformation"


@pytest.mark.anyio
async def test_wait_for_active_registry(mock_agent_controller: AcaPyClient):
    wallet_type = "askar"

    # Mock the get_created_active_registries function to return active registries
    with patch(
        "app.services.revocation_registry.get_created_active_registries",
        new_callable=AsyncMock,
    ) as mock_get_created_active_registries:
        mock_get_created_active_registries.side_effect = [
            [],  # First call returns no active registries
            ["reg_id_1"],  # Second call returns one active registry
            ["reg_id_1", "reg_id_2"],  # Third call returns two active registries
        ]

        # Mock asyncio.sleep to avoid actual delay
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            active_registries = await test_module.wait_for_active_registry(
                controller=mock_agent_controller,
                cred_def_id=cred_def_id,
                wallet_type=wallet_type,
            )

            # Verify the result
            assert active_registries == ["reg_id_1", "reg_id_2"]

            # Verify that asyncio.sleep was called thrice (first one = 0)
            assert mock_sleep.call_count == 3

            # Verify that get_created_active_registries was called three times
            assert mock_get_created_active_registries.call_count == 3

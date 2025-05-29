from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import RequestInfo
from aries_cloudcontroller import AcaPyClient
from pytest_mock import MockerFixture

import app.routes.issuer as test_module
from app.dependencies.auth import AcaPyAuth
from app.exceptions import CloudApiException
from app.models.issuer import AnonCredsCredential, CredentialBase
from app.services.issuer.acapy_issuer_v2 import IssuerV2
from shared.models.credential_exchange import CredentialExchange
from shared.util.mock_agent_controller import MockContextManagedController

did = "did:sov:WgWxqztrNooG92RXvxSTWv"
cred_def_id = "WgWxqztrNooG92RXvxSTWv:1:12345:tag"


@pytest.mark.anyio
async def test_send_credential(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    cred_ex = MagicMock(spec=CredentialExchange)

    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    mock_assert_valid_issuer = mocker.patch.object(
        test_module, "assert_valid_issuer", new=AsyncMock(return_value=True)
    )
    mock_schema_id_from_credential_definition_id = mocker.patch.object(
        test_module,
        "schema_id_from_credential_definition_id",
        new=AsyncMock(return_value="schema_id"),
    )
    mocker.patch(
        "app.util.valid_issuer.assert_public_did", new=AsyncMock(return_value=did)
    )

    IssuerV2.send_credential = AsyncMock(return_value=cred_ex)

    credential = test_module.SendCredential(
        connection_id="conn_id",
        anoncreds_credential_detail=AnonCredsCredential(
            credential_definition_id=cred_def_id,
            attributes={"name": "John", "age": "23"},
        ),
    )

    result = await test_module.send_credential(credential, mock_tenant_auth)

    assert result is cred_ex
    IssuerV2.send_credential.assert_called_once()

    mock_schema_id_from_credential_definition_id.assert_called_once_with(
        mock_agent_controller, cred_def_id
    )
    mock_assert_valid_issuer.assert_called_once_with(did, "schema_id")

    request_info = MagicMock(spec=RequestInfo)
    request_info.real_url = "www.real.co.za"

    mocker.patch.object(
        test_module, "assert_valid_issuer", new=AsyncMock(return_value=True)
    )
    mocker.patch(
        "app.util.valid_issuer.assert_public_did", new=AsyncMock(return_value=did)
    )
    mocker.patch.object(
        test_module,
        "schema_id_from_credential_definition_id",
        new=AsyncMock(return_value="schema_id"),
    )
    IssuerV2.send_credential = AsyncMock(side_effect=CloudApiException("abc"))

    with pytest.raises(CloudApiException):
        await test_module.send_credential(credential, mock_tenant_auth)


@pytest.mark.anyio
async def test_get_credentials(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    v2_records_no_conn_id = [
        MagicMock(spec=CredentialExchange),
        MagicMock(spec=CredentialExchange),
    ]
    v2_records = [MagicMock(spec=CredentialExchange)]

    IssuerV2.get_records = AsyncMock(return_value=v2_records_no_conn_id)

    result = await test_module.get_credentials(
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        state=None,
        thread_id=None,
        role=None,
        auth=mock_tenant_auth,
    )

    assert result == v2_records_no_conn_id

    IssuerV2.get_records.assert_called_once_with(
        controller=mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id=None,
        state=None,
        thread_id=None,
        role=None,
    )

    IssuerV2.get_records = AsyncMock(return_value=v2_records)

    result = await test_module.get_credentials(
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id="conn_id",
        role="issuer",
        state="done",
        thread_id="thread",
        auth=mock_tenant_auth,
    )

    assert result == v2_records
    IssuerV2.get_records.assert_called_once_with(
        controller=mock_agent_controller,
        limit=100,
        offset=0,
        order_by="id",
        descending=True,
        connection_id="conn_id",
        role="issuer",
        state="done",
        thread_id="thread",
    )


@pytest.mark.anyio
async def test_get_credential(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    v2_record = MagicMock(spec=CredentialExchange)
    IssuerV2.get_record = AsyncMock(return_value=v2_record)

    result = await test_module.get_credential(
        "v2-credential_exchange_id", mock_tenant_auth
    )

    assert result is v2_record
    IssuerV2.get_record.assert_called_once_with(
        controller=mock_agent_controller,
        credential_exchange_id="v2-credential_exchange_id",
    )


@pytest.mark.anyio
async def test_remove_credential_exchange_record(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    v2_record = MagicMock(spec=CredentialExchange)
    IssuerV2.delete_credential_exchange_record = AsyncMock(return_value=v2_record)

    await test_module.remove_credential_exchange_record(
        "v2-credential_exchange_id", mock_tenant_auth
    )

    IssuerV2.delete_credential_exchange_record.assert_called_once_with(
        controller=mock_agent_controller,
        credential_exchange_id="v2-credential_exchange_id",
    )


@pytest.mark.anyio
async def test_request_credential(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    v2_record = MagicMock(spec=CredentialExchange)
    ld_record = MagicMock(spec=CredentialExchange)

    v2_record.credential_definition_id = "WgWxqztrNooG92RXvxSTWv:other:parts"
    v2_record.schema_id = "schema_id2"
    v2_record.type = "anoncreds"

    ld_record.type = "ld_proof"
    ld_record.did = did

    IssuerV2.request_credential = AsyncMock(return_value=v2_record)
    IssuerV2.get_record = AsyncMock(return_value=v2_record)
    test_module.assert_valid_issuer = AsyncMock(return_value=True)

    await test_module.request_credential(
        "v2-credential_exchange_id", auth=mock_tenant_auth
    )

    IssuerV2.request_credential.assert_called_once_with(
        controller=mock_agent_controller,
        credential_exchange_id="v2-credential_exchange_id",
        auto_remove=None,
    )
    test_module.assert_valid_issuer.assert_called_once_with(did, "schema_id2")

    # Test for ld_record
    IssuerV2.request_credential = AsyncMock(return_value=ld_record)
    IssuerV2.get_record = AsyncMock(return_value=ld_record)
    test_module.assert_valid_issuer = AsyncMock(return_value=True)

    await test_module.request_credential(
        "v2-credential_exchange_id", auth=mock_tenant_auth
    )

    IssuerV2.request_credential.assert_called_once_with(
        controller=mock_agent_controller,
        credential_exchange_id="v2-credential_exchange_id",
        auto_remove=None,
    )
    test_module.assert_valid_issuer.assert_called_once_with(did, None)


@pytest.mark.anyio
async def test_request_credential_x_no_schema_cred_def(mock_tenant_auth: AcaPyAuth):
    v2_record = MagicMock(spec=CredentialExchange)

    v2_record.credential_definition_id = None
    v2_record.schema_id = None
    v2_record.type = "anoncreds"
    IssuerV2.get_record = AsyncMock(return_value=v2_record)

    with pytest.raises(
        Exception, match="Record has no credential definition or schema associated."
    ):
        await test_module.request_credential(
            "v2-credential_exchange_id", auth=mock_tenant_auth
        )

        IssuerV2.request_credential.assert_not_called()
        test_module.assert_valid_issuer.assert_not_called()


@pytest.mark.anyio
async def test_store_credential(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )

    v2_record = MagicMock(spec=CredentialExchange)
    IssuerV2.store_credential = AsyncMock(return_value=v2_record)

    await test_module.store_credential("v2-credential_exchange_id2", mock_tenant_auth)

    IssuerV2.store_credential.assert_called_once_with(
        controller=mock_agent_controller,
        credential_exchange_id="v2-credential_exchange_id2",
    )


@pytest.mark.anyio
async def test_create_offer(
    mock_agent_controller: AcaPyClient,
    mock_context_managed_controller: MockContextManagedController,
    mock_tenant_auth: AcaPyAuth,
    mocker: MockerFixture,
):
    mocker.patch.object(
        test_module,
        "client_from_auth",
        return_value=mock_context_managed_controller(mock_agent_controller),
    )
    v2_credential = MagicMock(spec=CredentialBase)

    v2_record = MagicMock(spec=CredentialExchange)
    IssuerV2.create_offer = AsyncMock(return_value=v2_record)

    mocker.patch(
        "app.util.valid_issuer.assert_public_did", new=AsyncMock(return_value=did)
    )
    test_module.assert_valid_issuer = AsyncMock(return_value=True)

    await test_module.create_offer(v2_credential, mock_tenant_auth)

    IssuerV2.create_offer.assert_called_once_with(
        controller=mock_agent_controller, credential=v2_credential
    )

from unittest.mock import patch

import pytest
from aiohttp import RequestInfo
from aries_cloudcontroller import AcaPyClient
from mockito import mock, verify, when
from pytest_mock import MockerFixture

import app.routes.issuer as test_module
from app.dependencies.auth import AcaPyAuth
from app.exceptions import CloudApiException
from app.models.issuer import CredentialBase, IndyCredential
from app.services.issuer.acapy_issuer_v2 import IssuerV2
from app.tests.util.mock import to_async
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
    with patch("app.routes.issuer.get_wallet_type", return_value="askar"):
        cred_ex = mock(CredentialExchange)

        mocker.patch.object(
            test_module,
            "client_from_auth",
            return_value=mock_context_managed_controller(mock_agent_controller),
        )

        when(test_module).assert_valid_issuer(...).thenReturn(to_async(True))
        when(test_module).schema_id_from_credential_definition_id(
            mock_agent_controller, cred_def_id, "askar"
        ).thenReturn(to_async("schema_id"))
        when(IssuerV2).send_credential(...).thenReturn(to_async(cred_ex))
        when(test_module).assert_public_did(...).thenReturn(to_async(did))

        credential = test_module.SendCredential(
            connection_id="conn_id",
            indy_credential_detail=IndyCredential(
                credential_definition_id=cred_def_id,
                attributes={"name": "John", "age": "23"},
            ),
        )

        result = await test_module.send_credential(credential, mock_tenant_auth)

        assert result is cred_ex
        verify(IssuerV2).send_credential(...)
        verify(test_module).schema_id_from_credential_definition_id(
            mock_agent_controller, cred_def_id, "askar"
        )
        verify(test_module).assert_public_did(mock_agent_controller)
        verify(test_module).assert_valid_issuer(did, "schema_id")

        request_info = mock(RequestInfo)
        request_info.real_url = "www.real.co.za"

        when(test_module).assert_valid_issuer(...).thenReturn(to_async(True))
        when(test_module).assert_public_did(...).thenReturn(to_async(did))
        when(test_module).schema_id_from_credential_definition_id(
            mock_agent_controller, cred_def_id, "askar"
        ).thenReturn(to_async("schema_id"))
        when(IssuerV2).send_credential(...).thenRaise(CloudApiException("abc"))

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

    v2_records_no_conn_id = [mock(CredentialExchange), mock(CredentialExchange)]

    v2_records = [mock(CredentialExchange)]

    with when(IssuerV2).get_records(...).thenReturn(to_async(v2_records_no_conn_id)):
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

        verify(IssuerV2).get_records(
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

    with when(IssuerV2).get_records(...).thenReturn(to_async(v2_records)):
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
        verify(IssuerV2).get_records(
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

    v2_record = mock(CredentialExchange)

    with when(IssuerV2).get_record(...).thenReturn(to_async(v2_record)):
        result = await test_module.get_credential(
            "v2-credential_exchange_id", mock_tenant_auth
        )

        assert result is v2_record
        verify(IssuerV2).get_record(
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

    v2_record = mock(CredentialExchange)

    with when(IssuerV2).delete_credential_exchange_record(...).thenReturn(
        to_async(v2_record)
    ):
        await test_module.remove_credential_exchange_record(
            "v2-credential_exchange_id", mock_tenant_auth
        )

        verify(IssuerV2).delete_credential_exchange_record(
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

    v2_record = mock(CredentialExchange)
    ld_record = mock(CredentialExchange)

    v2_record.credential_definition_id = "WgWxqztrNooG92RXvxSTWv:other:parts"
    v2_record.schema_id = "schema_id2"
    v2_record.type = "indy"

    ld_record.type = "ld_proof"
    ld_record.did = did

    with when(IssuerV2).request_credential(...).thenReturn(to_async(v2_record)), when(
        IssuerV2
    ).get_record(...).thenReturn(to_async(v2_record)), when(
        test_module
    ).assert_valid_issuer(
        ...
    ).thenReturn(
        to_async(True)
    ):
        await test_module.request_credential(
            "v2-credential_exchange_id", auth=mock_tenant_auth
        )

        verify(IssuerV2).request_credential(
            controller=mock_agent_controller,
            credential_exchange_id="v2-credential_exchange_id",
            auto_remove=None,
        )
        verify(test_module).assert_valid_issuer(did, "schema_id2")

    with when(IssuerV2).request_credential(...).thenReturn(to_async(ld_record)), when(
        IssuerV2
    ).get_record(...).thenReturn(to_async(ld_record)), when(
        test_module
    ).assert_valid_issuer(
        ...
    ).thenReturn(
        to_async(True)
    ):
        await test_module.request_credential(
            "v2-credential_exchange_id", auth=mock_tenant_auth
        )

        verify(IssuerV2).request_credential(
            controller=mock_agent_controller,
            credential_exchange_id="v2-credential_exchange_id",
            auto_remove=None,
        )
        verify(test_module).assert_valid_issuer(did, None)


@pytest.mark.anyio
async def test_request_credential_x_no_schema_cred_def(
    mock_agent_controller: AcaPyClient,
    mock_tenant_auth: AcaPyAuth,
):
    v2_record = mock(CredentialExchange)

    v2_record.credential_definition_id = None
    v2_record.schema_id = None
    v2_record.type = "indy"

    with when(IssuerV2).get_record(...).thenReturn(to_async(v2_record)), pytest.raises(
        Exception, match="Record has no credential definition or schema associated."
    ):
        await test_module.request_credential(
            "v2-credential_exchange_id", auth=mock_tenant_auth
        )

        verify(IssuerV2, times=0).request_credential(
            controller=mock_agent_controller,
            credential_exchange_id="credential_exchange_id",
        )
        verify(test_module, times=0).assert_valid_issuer(did, "schema_id1")


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

    v2_record = mock(CredentialExchange)

    when(IssuerV2).store_credential(...).thenReturn(to_async(v2_record))

    await test_module.store_credential("v2-credential_exchange_id2", mock_tenant_auth)

    verify(IssuerV2).store_credential(
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
    with patch("app.routes.issuer.get_wallet_type", return_value="askar"):

        mocker.patch.object(
            test_module,
            "client_from_auth",
            return_value=mock_context_managed_controller(mock_agent_controller),
        )
        v2_credential = mock(CredentialBase)

        v2_credential.type = "Indy"

        v2_record = mock(CredentialExchange)

        when(IssuerV2).create_offer(...).thenReturn(to_async(v2_record))

        when(test_module).assert_public_did(...).thenReturn(to_async(did))
        when(test_module).assert_valid_issuer(...).thenReturn(to_async(True))
        await test_module.create_offer(v2_credential, mock_tenant_auth)

        verify(IssuerV2).create_offer(
            controller=mock_agent_controller, credential=v2_credential
        )

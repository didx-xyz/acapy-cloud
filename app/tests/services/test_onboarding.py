import pytest
from aries_cloudcontroller import (
    DID,
    AcaPyClient,
    ConnRecord,
    InvitationCreateRequest,
    InvitationMessage,
    InvitationRecord,
)
from assertpy import assert_that
from mockito import verify, when

from app.exceptions import CloudApiException
from app.services import acapy_ledger, acapy_wallet
from app.services.event_handling.sse_listener import SseListener
from app.services.onboarding import issuer, verifier
from app.services.onboarding.util import register_issuer_did
from app.tests.util.mock import to_async
from shared.constants import GOVERNANCE_LABEL
from shared.util.mock_agent_controller import get_mock_agent_controller

did_object = DID(
    did="WgWxqztrNooG92RXvxSTWv",
    verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
)


@pytest.mark.anyio
async def test_onboard_issuer_public_did_exists(
    mock_agent_controller: AcaPyClient,
):
    when(acapy_wallet).get_public_did(controller=mock_agent_controller).thenReturn(
        to_async(did_object)
    )

    endorser_controller = get_mock_agent_controller()

    when(endorser_controller.out_of_band).create_invitation(...).thenReturn(
        InvitationRecord(invitation=InvitationMessage())
    )
    when(mock_agent_controller.out_of_band).receive_invitation(...).thenReturn(
        ConnRecord()
    )

    when(acapy_wallet).get_public_did(controller=endorser_controller).thenReturn(
        did_object
    )

    when(mock_agent_controller.endorse_transaction).set_endorser_role(...).thenReturn(
        None
    )
    when(endorser_controller.endorse_transaction).set_endorser_role(...).thenReturn(
        None
    )
    when(mock_agent_controller.endorse_transaction).set_endorser_info(...).thenReturn(
        None
    )

    # Mock event listeners
    when(register_issuer_did).create_sse_listener(
        topic="connections", wallet_id=GOVERNANCE_LABEL
    ).thenReturn(MockSseListener(topic="connections", wallet_id=GOVERNANCE_LABEL))
    when(register_issuer_did).create_sse_listener(
        topic="endorsements", wallet_id=GOVERNANCE_LABEL
    ).thenReturn(
        MockListenerEndorserConnectionId(
            topic="endorsements", wallet_id=GOVERNANCE_LABEL
        )
    )

    invitation_url = "https://invitation.com/"

    when(mock_agent_controller.out_of_band).create_invitation(...).thenReturn(
        to_async(
            InvitationRecord(
                invitation_url=invitation_url,
            )
        )
    )

    onboard_result = await issuer.onboard_issuer(
        issuer_label="issuer_name",
        endorser_controller=endorser_controller,
        issuer_controller=mock_agent_controller,
        issuer_wallet_id="issuer_wallet_id",
    )

    assert_that(onboard_result).has_did("did:sov:WgWxqztrNooG92RXvxSTWv")


@pytest.mark.anyio
async def test_onboard_issuer_no_public_did(
    mock_agent_controller: AcaPyClient,
):
    endorser_controller = get_mock_agent_controller()

    when(acapy_wallet).get_public_did(controller=mock_agent_controller).thenRaise(
        CloudApiException(detail="Error")
    )
    when(acapy_wallet).get_public_did(controller=endorser_controller).thenReturn(
        to_async(did_object)
    )

    when(endorser_controller.out_of_band).create_invitation(...).thenReturn(
        to_async(InvitationRecord(invitation=InvitationMessage()))
    )

    # Mock event listeners
    when(register_issuer_did).create_sse_listener(
        topic="connections", wallet_id=GOVERNANCE_LABEL
    ).thenReturn(
        MockListenerEndorserConnectionId(
            topic="connections", wallet_id=GOVERNANCE_LABEL
        )
    )
    when(register_issuer_did).create_sse_listener(
        topic="endorsements", wallet_id=GOVERNANCE_LABEL
    ).thenReturn(
        MockListenerRequestReceived(topic="endorsements", wallet_id=GOVERNANCE_LABEL)
    )

    # Mock responses
    when(mock_agent_controller.out_of_band).receive_invitation(...).thenReturn(
        to_async(ConnRecord())
    )
    when(mock_agent_controller.endorse_transaction).set_endorser_role(...).thenReturn(
        to_async()
    )

    when(endorser_controller.endorse_transaction).set_endorser_role(...).thenReturn(
        to_async()
    )
    when(mock_agent_controller.endorse_transaction).set_endorser_info(...).thenAnswer(
        lambda conn_id, endorser_did: to_async()
    )

    when(acapy_wallet).create_did(mock_agent_controller).thenReturn(
        to_async(did_object)
    )
    when(acapy_ledger).register_nym_on_ledger(...).thenReturn(to_async())
    when(acapy_ledger).accept_taa_if_required(...).thenReturn(to_async())
    when(acapy_wallet).set_public_did(...).thenReturn(to_async())
    when(endorser_controller.endorse_transaction).endorse_transaction(...).thenReturn(
        to_async()
    )

    # Create an invitation as well
    invitation_url = "https://invitation.com/"
    when(mock_agent_controller.out_of_band).create_invitation(...).thenReturn(
        to_async(
            InvitationRecord(
                invitation_url=invitation_url,
            )
        )
    )

    onboard_result = await issuer.onboard_issuer(
        issuer_label="issuer_name",
        endorser_controller=endorser_controller,
        issuer_controller=mock_agent_controller,
        issuer_wallet_id="issuer_wallet_id",
    )

    assert_that(onboard_result).has_did("did:sov:WgWxqztrNooG92RXvxSTWv")
    verify(acapy_wallet).create_did(mock_agent_controller)
    verify(acapy_ledger).register_nym_on_ledger(
        endorser_controller,
        did="WgWxqztrNooG92RXvxSTWv",
        verkey="WgWxqztrNooG92RXvxSTWvWgWxqztrNooG92RXvxSTWv",
        alias="issuer_name",
    )
    verify(acapy_ledger).accept_taa_if_required(mock_agent_controller)
    verify(acapy_wallet).set_public_did(
        mock_agent_controller,
        did="WgWxqztrNooG92RXvxSTWv",
        create_transaction_for_endorser=True,
    )


@pytest.mark.anyio
async def test_onboard_verifier_public_did_exists(mock_agent_controller: AcaPyClient):
    when(acapy_wallet).get_public_did(controller=mock_agent_controller).thenReturn(
        to_async(did_object)
    )

    onboard_result = await verifier.onboard_verifier(
        verifier_label="verifier_name", verifier_controller=mock_agent_controller
    )

    assert_that(onboard_result).has_did("did:sov:WgWxqztrNooG92RXvxSTWv")
    verify(acapy_wallet).get_public_did(controller=mock_agent_controller)


@pytest.mark.anyio
async def test_onboard_verifier_no_public_did(mock_agent_controller: AcaPyClient):
    when(acapy_wallet).get_public_did(controller=mock_agent_controller).thenRaise(
        CloudApiException(detail="No public did found")
    )

    did_key = "did:key:123"
    invitation_url = "https://invitation.com/"

    when(mock_agent_controller.out_of_band).create_invitation(...).thenReturn(
        to_async(
            InvitationRecord(
                invitation_url=invitation_url,
                invitation=InvitationMessage(services=[{"recipientKeys": [did_key]}]),
            )
        )
    )

    onboard_result = await verifier.onboard_verifier(
        verifier_label="verifier_name", verifier_controller=mock_agent_controller
    )

    assert_that(onboard_result).has_did(did_key)
    assert str(onboard_result.didcomm_invitation) == invitation_url
    verify(mock_agent_controller.out_of_band).create_invitation(
        auto_accept=True,
        multi_use=True,
        body=InvitationCreateRequest(
            use_public_did=False,
            alias="Trust Registry verifier_name",
            handshake_protocols=["https://didcomm.org/didexchange/1.0"],
        ),
    )


@pytest.mark.anyio
async def test_onboard_verifier_no_recipient_keys(mock_agent_controller: AcaPyClient):
    when(acapy_wallet).get_public_did(controller=mock_agent_controller).thenRaise(
        CloudApiException(detail="No public did found")
    )
    when(mock_agent_controller.out_of_band).create_invitation(...).thenReturn(
        to_async(
            InvitationRecord(
                invitation=InvitationMessage(services=[{"recipientKeys": []}]),
            )
        )
    )

    with pytest.raises(CloudApiException):
        await verifier.onboard_verifier(
            verifier_label="verifier_name", verifier_controller=mock_agent_controller
        )


class MockSseListener(SseListener):
    async def wait_for_event(
        self, field, field_id, desired_state, timeout: int = 150, lookback_time=1
    ):
        pass


class MockListenerEndorserConnectionId(MockSseListener):
    async def wait_for_event(
        self, field, field_id, desired_state, timeout: int = 150, lookback_time=1
    ):
        return {"connection_id": "endorser_connection_id"}


class MockListenerRequestReceived(MockSseListener):
    async def wait_for_state(self, desired_state, timeout: int = 150, lookback_time=1):
        return {"state": "request-received", "transaction_id": "abcde"}

from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    AttachmentDef,
    InvitationCreateRequest,
    InvitationRecord,
)

from app.models.oob import CreateOobInvitation
from app.routes.oob import create_oob_invitation

test_invitation_record = InvitationRecord(
    invitation_url="https://example.com?oob=12345",
    invitation_msg={},
    invitation_id="some_invitation_id",
)

test_attachments = [AttachmentDef(id="test_id", type="credential-offer")]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        None,
        CreateOobInvitation(create_connection=True),
        CreateOobInvitation(attachments=test_attachments),
    ],
)
async def test_create_oob_invitation_success(body) -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.out_of_band.create_invitation = AsyncMock(
        return_value=test_invitation_record
    )
    handshake_protocols = [
        "https://didcomm.org/didexchange/1.1",
    ]
    if body and body.attachments:
        handshake_protocols = None

    create_request = InvitationCreateRequest(
        alias=body.alias if body else None,
        attachments=body.attachments if body else None,
        handshake_protocols=handshake_protocols,
        use_public_did=body.use_public_did if body else None,
    )
    with patch("app.routes.oob.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await create_oob_invitation(
            body=body,
            auth="mocked_auth",
        )

        assert response == test_invitation_record

        mock_aries_controller.out_of_band.create_invitation.assert_awaited_once_with(
            multi_use=body.multi_use if body else None,
            body=create_request,
            auto_accept=True,
        )

from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import OobRecord

from app.models.oob import AcceptOobInvitation
from app.routes.oob import accept_oob_invitation

test_oob_record = OobRecord(
    invi_msg_id="some_invitation_id",
    invitation={},
    oob_id="some_oob_id",
    state="await-response",
)


@pytest.mark.anyio
async def test_accept_oob_invitation_success() -> None:
    mock_aries_controller = AsyncMock()
    mock_aries_controller.out_of_band.receive_invitation = AsyncMock(
        return_value=test_oob_record
    )
    body = AcceptOobInvitation(
        alias="test_alias",
        use_existing_connection=False,
        invitation={},
    )
    with patch("app.routes.oob.client_from_auth") as mock_client_from_auth:
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        response = await accept_oob_invitation(
            body=body,
            auth="mocked_auth",
        )

        assert response == test_oob_record

        mock_aries_controller.out_of_band.receive_invitation.assert_awaited_once_with(
            auto_accept=True,
            use_existing_connection=body.use_existing_connection,
            alias=body.alias,
            body=body.invitation,
        )

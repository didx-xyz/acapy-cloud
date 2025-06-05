from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import CreateCheqdDIDRequest
from aries_cloudcontroller import DIDCreate as DIDCreateAcaPy
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    NotFoundException,
)

from app.models.wallet import DIDCreate
from app.routes.wallet.dids import create_did


@pytest.mark.anyio
@pytest.mark.parametrize(
    "request_body, create_body",
    [
        (
            None,
            CreateCheqdDIDRequest(options={"key_type": "ed25519"}),
        ),
        (
            DIDCreate(method="key"),
            DIDCreateAcaPy(
                method="key",
                options={"key_type": "ed25519"},
            ),
        ),
        (
            DIDCreate(method="sov"),
            DIDCreateAcaPy(
                method="sov",
                options={"key_type": "ed25519"},
            ),
        ),
        (
            DIDCreate(method="did:peer:2"),
            DIDCreateAcaPy(
                method="did:peer:2",
                options={"key_type": "ed25519"},
            ),
        ),
        (
            DIDCreate(method="did:peer:4"),
            DIDCreateAcaPy(
                method="did:peer:4",
                options={"key_type": "ed25519"},
            ),
        ),
        (
            DIDCreate(method="key", key_type="bls12381g2"),
            DIDCreateAcaPy(
                method="key",
                options={"key_type": "bls12381g2"},
            ),
        ),
        (
            DIDCreate(method="sov", key_type="bls12381g2"),
            DIDCreateAcaPy(
                method="sov",
                options={"key_type": "bls12381g2"},
            ),
        ),
        (
            DIDCreate(method="did:peer:2", key_type="bls12381g2"),
            DIDCreateAcaPy(
                method="did:peer:2",
                options={"key_type": "bls12381g2"},
            ),
        ),
        (
            DIDCreate(method="did:peer:4", key_type="bls12381g2"),
            DIDCreateAcaPy(
                method="did:peer:4",
                options={"key_type": "bls12381g2"},
            ),
        ),
        (
            DIDCreate(method="web", did="did:web:1234"),
            DIDCreateAcaPy(
                method="web",
                options={"key_type": "ed25519", "did": "did:web:1234"},
            ),
        ),
        (
            DIDCreate(method="web", key_type="bls12381g2", did="did:web:1234"),
            DIDCreateAcaPy(
                method="web",
                options={"key_type": "bls12381g2", "did": "did:web:1234"},
            ),
        ),
    ],
)
async def test_create_did_success(request_body, create_body):
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        patch("app.services.acapy_wallet.handle_acapy_call") as mock_handle_acapy_call,
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        if request_body is None:
            acapy_call = mock_aries_controller.did.did_cheqd_create_post
            mock_handle_acapy_call.return_value = AsyncMock(
                did="did:cheqd:1234",
                verkey="a" * 131,  # Expected verkey length
            )
        else:
            acapy_call = mock_aries_controller.wallet.create_did
            mock_handle_acapy_call.return_value = AsyncMock(
                did=f"did:{request_body.method}:1234", verkey="1234"
            )

        await create_did(did_create=request_body, auth="mocked_auth")

        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock.ANY,
            acapy_call=acapy_call,
            body=create_body,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception_class, expected_status_code, expected_detail",
    [
        (BadRequestException, 400, "Bad request"),
        (NotFoundException, 404, "Not found"),
        (ApiException, 500, "Internal Server Error"),
    ],
)
async def test_create_did_fail_acapy_error(
    exception_class, expected_status_code, expected_detail
):
    mock_aries_controller = AsyncMock()
    mock_create_did = AsyncMock(
        side_effect=exception_class(status=expected_status_code, reason=expected_detail)
    )

    with (
        patch("app.routes.wallet.dids.client_from_auth") as mock_client_from_auth,
        pytest.raises(exception_class, match=expected_detail) as exc,
        patch("app.services.acapy_wallet.create_did", mock_create_did),
    ):
        # Configure client_from_auth to return our mocked aries_controller on enter
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )

        await create_did(auth="mocked_auth")

    assert exc.value.status == expected_status_code

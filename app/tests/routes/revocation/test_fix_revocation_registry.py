from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import RevRegWalletUpdatedResult

from app.routes.revocation import fix_revocation_registry_entry_state

rev_reg_id_valid = (
    "RiDathgbUA5Z9fYTqF35Jd:4:RiDathgbUA5Z9fYTqF35Jd:3:CL:8:Epic"
    ":CL_ACCUM:1dae952e-b58a-4269-a4b7-526ae1c69156"
)

rev_reg_no_update = RevRegWalletUpdatedResult(
    accum_calculated={
        "ver": "1.0",
        "value": {
            "prevAccum": "21 some_value FF",
            "accum": "21 some_other_value 56",
            "revoked": [14, 23, 21, 7, 5],
        },
    },
    accum_fixed={},
    rev_reg_delta={
        "ver": "1.0",
        "value": {
            "accum": "21 some_value FF",
            "issued": [],
            "revoked": [1, 3, 17],
        },
    },
)

rev_reg_update = RevRegWalletUpdatedResult(
    accum_calculated={
        "ver": "1.0",
        "value": {
            "prevAccum": "21 some_value FF",
            "accum": "21 some_new_value 56",
            "revoked": [23, 21, 7, 14, 5],
        },
    },
    accum_fixed={
        "txn": {
            "type": "114",
            "data": {
                "revocDefType": "CL_ACCUM",
                "revocRegDefId": rev_reg_id_valid,
                "value": {
                    "accum": "21 some_new_value 56",
                    "prevAccum": "21 some-value FF",
                    "revoked": [23, 21, 7, 14, 5],
                },
            },
            "protocolVersion": 2,
            "metadata": {
                "from": "RiDathgbUA5Z9fYTqF35Jd",
                "reqId": 1732708291768573000,
                "taaAcceptance": {
                    "mechanism": "service_agreement",
                    "taaDigest": "0be4d87dec17a7901cb8ba8bb4239ee34d4f6e08906f3dad81d1d052dccc078f",
                    "time": 1732665600,
                },
                "digest": "cbbdd50e91571c1919e87823f7c4263817660335ba76276374dada33230dff01",
                "payloadDigest": "50886760cea64c365c8a84ef882ede28c8be4ceece2472c3c008c3e7c7e3720d",
            },
        },
        "txnMetadata": {
            "txnId": f"5:{rev_reg_id_valid}",
            "txnTime": 1732708291,
            "seqNo": 19,
        },
        "reqSignature": {
            "type": "ED25519",
            "values": [
                {
                    "from": "RiDathgbUA5Z9fYTqF35Jd",
                    "value": "2obhaXnyBvaFUBTw6z37Qt8LsX48v959JBQSueRnkc3cjC7Eqchi9x2K5TMDzomProbQ2r4GszSkL5LzZxdMQrvB",
                }
            ],
        },
        "ver": "1",
        "rootHash": "4yesC2SPB6SCri6vaJKF3Qu286q2qgqYoQYPazhP4sbE",
        "auditPath": [
            "ENZGPfL9Y4d76y3SLjSTjZr5sdnV5mbputNFbwgkYAA6",
            "3yhCxb4npZTA3DeTJ6priQUyLFYhfKXpUkUH6rsfcCfR",
        ],
    },
    rev_reg_delta={
        "ver": "1.0",
        "value": {
            "accum": "21 some_value FF",
            "issued": [],
            "revoked": [1, 3, 17],
        },
    },
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "rev_reg_id, apply_ledger_update, response",
    [
        (rev_reg_id_valid, False, rev_reg_no_update),
        (rev_reg_id_valid, True, rev_reg_update),
    ],
)
async def test_fix_revocation_registry_entry_state_success(
    rev_reg_id, apply_ledger_update, response
) -> None:
    mock_aries_controller = AsyncMock()

    with (
        patch("app.routes.revocation.client_from_auth") as mock_client_from_auth,
        patch(
            "app.routes.revocation.handle_acapy_call",
        ) as mock_handle_acapy_call,
        patch("app.routes.revocation.logger") as mock_logger,
    ):
        mock_client_from_auth.return_value.__aenter__.return_value = (
            mock_aries_controller
        )
        mock_handle_acapy_call.return_value = response

        result = await fix_revocation_registry_entry_state(
            revocation_registry_id=rev_reg_id,
            apply_ledger_update=apply_ledger_update,
            auth="mocked_auth",
        )

        mock_handle_acapy_call.assert_awaited_once_with(
            logger=mock_logger.bind(),
            acapy_call=mock_aries_controller.anoncreds_revocation.update_rev_reg_revoked_state,
            rev_reg_id=rev_reg_id,
            apply_ledger_update=apply_ledger_update,
        )

        assert response == result

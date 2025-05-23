from unittest.mock import AsyncMock, patch

import pytest
from aries_cloudcontroller import (
    CredDef,
    GetCredDefResult,
    GetCredDefsResponse,
)

from app.models.definitions import CredentialDefinition as CredDefModel
from app.services.definitions.credential_definitions import get_credential_definitions


@pytest.mark.anyio
async def test_get_credential_definitions_success():
    mock_aries_controller = AsyncMock()

    mock_cred_def_ids = [
        "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_1",
        "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_2",
    ]
    mock_anoncreds_cred_def_results = [
        GetCredDefResult(
            credential_definition_id="5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_1",
            credential_definition=CredDef(
                schema_id="schema_1",
                tag="tag_1",
            ),
        ),
        GetCredDefResult(
            credential_definition_id="5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_2",
            credential_definition=CredDef(
                schema_id="schema_2",
                tag="tag_2",
            ),
        ),
    ]

    with patch(
        "app.services.definitions.credential_definitions.handle_acapy_call"
    ) as mock_handle_acapy_call:
        mock_handle_acapy_call.side_effect = [
            GetCredDefsResponse(credential_definition_ids=mock_cred_def_ids),
            *mock_anoncreds_cred_def_results,
        ]
        result = await get_credential_definitions(mock_aries_controller)

        assert len(result) == 2
        assert all(isinstance(cred_def, CredDefModel) for cred_def in result)
        assert [cred_def.id for cred_def in result] == mock_cred_def_ids
        assert [cred_def.schema_id for cred_def in result] == ["schema_1", "schema_2"]
        assert [cred_def.tag for cred_def in result] == ["tag_1", "tag_2"]


@pytest.mark.anyio
async def test_get_credential_definitions_with_filters():
    mock_aries_controller = AsyncMock()

    mock_cred_def_ids = ["cred_def_1"]
    mock_cred_def_results = [
        GetCredDefResult(
            credential_definition_id = "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_1",
            credential_definition=CredDef(
                schema_id="schema_1",
                tag="tag_1",
            )
        )
    ]

    with patch(
        "app.services.definitions.credential_definitions.handle_acapy_call"
    ) as mock_handle_acapy_call:

        mock_handle_acapy_call.side_effect = [
            GetCredDefsResponse(
                credential_definition_ids=mock_cred_def_ids
            ),
            *mock_cred_def_results,
        ]

        result = await get_credential_definitions(
            mock_aries_controller,
            issuer_did="test_issuer_did",
            credential_definition_id="cred_def_1",
            schema_id="schema_1",
            schema_issuer_did="schema_issuer_did",
            schema_name="test_schema",
            schema_version="1.0",
        )

        assert len(result) == 1
        assert result[0].id == "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_1"
        mock_handle_acapy_call.assert_called()


@pytest.mark.anyio
async def test_get_credential_definitions_no_results():
    mock_aries_controller = AsyncMock()

    with patch(
        "app.services.definitions.credential_definitions.handle_acapy_call"
    ) as mock_handle_acapy_call:
        mock_handle_acapy_call.return_value = GetCredDefsResponse(
            credential_definition_ids=None
        )

        result = await get_credential_definitions(mock_aries_controller)

        assert len(result) == 0


@pytest.mark.anyio
async def test_get_credential_definitions_some_missing():
    mock_aries_controller = AsyncMock()

    mock_cred_def_ids = ["cred_def_1", "cred_def_2"]
    mock_cred_def_results = [
        GetCredDefResult(credential_definition=None),
        GetCredDefResult(
            credential_definition_id = "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_2",
            credential_definition=CredDef(
                schema_id="schema_2",
                tag="tag_2",
            )
        ),
    ]

    with patch(
        "app.services.definitions.credential_definitions.handle_acapy_call"
    ) as mock_handle_acapy_call:
        mock_handle_acapy_call.side_effect = [
            GetCredDefsResponse(
                credential_definition_ids=mock_cred_def_ids
            ),
            *mock_cred_def_results,
        ]

        result = await get_credential_definitions(mock_aries_controller)

        assert len(result) == 1
        assert result[0].id == "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:tag_2"

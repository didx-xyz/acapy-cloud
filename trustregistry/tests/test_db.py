from unittest.mock import MagicMock, patch

import pytest

from trustregistry.db import get_db, schema_id_gen


def test_schema_id_gen():
    mock_context = MagicMock()
    mock_context.get_current_parameters.return_value = {
        "did": "did",
        "name": "name",
        "version": "version",
    }
    assert schema_id_gen(mock_context) == "did:2:name:version"


def test_get_db():
    with patch("trustregistry.db.SessionLocal", autospec=True) as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        db_gen = get_db()

        db_session = next(db_gen)
        assert db_session is mock_session
        with pytest.raises(StopIteration):
            next(db_gen)

        mock_session.close.assert_called_once()

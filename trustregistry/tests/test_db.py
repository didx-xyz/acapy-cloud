from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trustregistry.db import get_async_db, get_db, schema_id_gen


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


@pytest.mark.anyio
async def test_get_async_db():
    with patch("trustregistry.db.AsyncSessionLocal") as mock_async_session_local:
        # Create a mock session
        mock_session = AsyncMock()

        # Create a mock async context manager that returns the session
        mock_session_instance = AsyncMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_instance.close = AsyncMock()

        # The session factory should return the context manager
        mock_async_session_local.return_value = mock_session_instance

        # Test the async generator
        async_db_gen = get_async_db()
        db_session = await async_db_gen.__anext__()

        assert db_session is mock_session

        # Test cleanup by finishing the generator
        try:
            await async_db_gen.__anext__()
        except StopAsyncIteration:
            pass

        # Verify session context manager was used
        mock_session_instance.__aenter__.assert_called_once()
        mock_session_instance.__aexit__.assert_called_once()


def test_schema_id_gen():
    context = MagicMock()
    context.get_current_parameters.return_value = {
        "did": "did:example:123",
        "name": "test_schema",
        "version": "1.0",
    }

    result = schema_id_gen(context)
    assert result == "did:example:123:2:test_schema:1.0"

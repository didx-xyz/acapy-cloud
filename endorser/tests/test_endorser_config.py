import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from endorser.services.endorser_config import EndorserConfig


@pytest.mark.anyio
async def test_singleton_behaviour():
    config1 = EndorserConfig()
    config2 = EndorserConfig()
    assert config1 is config2, "EndorserConfig should be a singleton"


@pytest.mark.anyio
async def test_initialize_wallet_type(mock_acapy_client):
    EndorserConfig().reset()  # Reset the singleton state
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "askar"}
    )

    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        config = EndorserConfig()
        await config.initialize()

    assert config.wallet_type == "askar", "Wallet type should be initialized to 'askar'"


@pytest.mark.anyio
async def test_initialize_wallet_type_askar_anoncreds(mock_acapy_client):
    EndorserConfig().reset()  # Reset the singleton state
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "askar-anoncreds"}
    )

    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        config = EndorserConfig()
        await config.initialize()

    assert (
        config.wallet_type == "askar-anoncreds"
    ), "Wallet type should be initialized to 'askar-anoncreds'"


@pytest.mark.anyio
async def test_initialize_invalid_wallet_type(mock_acapy_client):
    EndorserConfig().reset()  # Reset the singleton state
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "invalid-type"}
    )

    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        config = EndorserConfig()

        with pytest.raises(ValueError, match="Invalid wallet type: invalid-type"):
            await config.initialize()


@pytest.mark.anyio
async def test_initialize_only_once(mock_acapy_client):
    EndorserConfig().reset()  # Reset the singleton state
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "askar"}
    )

    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        config = EndorserConfig()
        await config.initialize()

    # Change the mock to return a different wallet type
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "askar-anoncreds"}
    )

    # Re-initialize should not change the wallet type
    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        await config.initialize()

        assert (
            config.wallet_type == "askar"
        ), "Wallet type should not change after first initialization"


@pytest.mark.anyio
async def test_concurrent_initialization(mock_acapy_client):
    EndorserConfig().reset()  # Reset the singleton state
    mock_acapy_client.server.get_config.return_value = AsyncMock(
        config={"wallet.type": "askar"}
    )

    with patch(
        "endorser.services.endorser_config.AcaPyClient", return_value=mock_acapy_client
    ):
        config = EndorserConfig()

        # Simulate concurrent initialization
        await asyncio.gather(config.initialize(), config.initialize())

    assert (
        config.wallet_type == "askar"
    ), "Wallet type should be initialized correctly even with concurrent calls"

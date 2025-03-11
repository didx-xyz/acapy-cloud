"""Utility functions for the governance wallet type"""

from typing import Literal

from aries_cloudcontroller import AcaPyClient

from shared.constants import GOVERNANCE_AGENT_API_KEY, GOVERNANCE_AGENT_URL
from shared.log_config import get_logger

logger = get_logger(__name__)


class EndorserConfig:
    """Singleton class for managing endorser configuration."""

    _instance = None
    _initialized = False

    def __new__(cls) -> "EndorserConfig":
        if cls._instance is None:
            cls._instance = super(EndorserConfig, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._wallet_type = None
            self._initialized = True

    @property
    def wallet_type(self) -> Literal["askar", "askar-anoncreds"]:
        return self._wallet_type

    async def initialize(self) -> None:
        """Initialize the wallet type if not already set"""
        if self._wallet_type is None:
            self._wallet_type = await self._get_wallet_type()

    async def _get_wallet_type(self) -> Literal["askar", "askar-anoncreds"]:
        """Get the governance wallet type"""
        async with AcaPyClient(
            base_url=GOVERNANCE_AGENT_URL, api_key=GOVERNANCE_AGENT_API_KEY
        ) as client:
            server_config = await client.server.get_config()
            wallet_type = server_config.config.get("wallet.type")
            if wallet_type not in ["askar", "askar-anoncreds"]:
                logger.critical("Invalid wallet type: `{}`", wallet_type)
                raise ValueError(f"Invalid wallet type: {wallet_type}")

        return wallet_type

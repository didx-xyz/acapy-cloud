from unittest.mock import AsyncMock, Mock

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    AnonCredsRevocationApi,
    AnonCredsSchemasApi,
    ConnectionApi,
    CredentialsApi,
    DidApi,
    EndorseTransactionApi,
    IssueCredentialV20Api,
    LedgerApi,
    OutOfBandApi,
    PresentProofV20Api,
    RevocationApi,
    SchemaApi,
    WalletApi,
)

from app.dependencies.auth import AcaPyAuth, AcaPyAuthVerified
from app.dependencies.role import Role
from shared.constants import GOVERNANCE_AGENT_API_KEY, GOVERNANCE_LABEL


async def noop():
    return None


def get_mock_agent_controller() -> AcaPyClient:
    controller = Mock(spec=AcaPyClient)
    controller.__aexit__ = AsyncMock(return_value=None)
    controller.anoncreds_revocation = Mock(spec=AnonCredsRevocationApi)
    controller.anoncreds_schemas = Mock(spec=AnonCredsSchemasApi)
    controller.connection = Mock(spec=ConnectionApi)
    controller.credentials = Mock(spec=CredentialsApi)
    controller.did = Mock(spec=DidApi)
    controller.endorse_transaction = Mock(spec=EndorseTransactionApi)
    controller.issue_credential_v2_0 = Mock(spec=IssueCredentialV20Api)
    controller.ledger = Mock(spec=LedgerApi)
    controller.out_of_band = Mock(spec=OutOfBandApi)
    controller.present_proof_v2_0 = Mock(spec=PresentProofV20Api)
    controller.revocation = Mock(spec=RevocationApi)
    controller.schema = Mock(spec=SchemaApi)
    controller.wallet = Mock(spec=WalletApi)
    return controller


class MockContextManagedController:
    def __init__(self, controller):
        """Initialize the mock context managed controller."""
        self.controller = controller

    async def __aenter__(self):
        """Enter mock context manager"""
        return self.controller

    async def __aexit__(self, exc_type, exc, tb):
        """Exit mock context manager"""
        pass


@pytest.fixture
def mock_agent_controller():
    return get_mock_agent_controller()


@pytest.fixture
def mock_context_managed_controller():
    return MockContextManagedController


@pytest.fixture(scope="session")
def mock_governance_auth() -> AcaPyAuthVerified:
    auth = AcaPyAuthVerified(
        role=Role.GOVERNANCE,
        token=GOVERNANCE_AGENT_API_KEY,
        wallet_id=GOVERNANCE_LABEL,
    )
    return auth


@pytest.fixture
def mock_admin_auth() -> AcaPyAuthVerified:
    auth = AcaPyAuthVerified(
        role=Role.TENANT_ADMIN,
        token=GOVERNANCE_AGENT_API_KEY,
        wallet_id="admin",
    )
    return auth


@pytest.fixture
def mock_tenant_auth() -> AcaPyAuth:
    auth = AcaPyAuth(
        role=Role.TENANT,
        token="tenant.test_token",
    )
    return auth


@pytest.fixture
def mock_tenant_auth_verified() -> AcaPyAuthVerified:
    auth = AcaPyAuthVerified(
        role=Role.TENANT,
        token="tenant.test_token",
        wallet_id="tenant_wallet_id",
    )
    return auth

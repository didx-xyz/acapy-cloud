from unittest.mock import AsyncMock, Mock

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    AnoncredsRevocationApi,
    AnoncredsSchemasApi,
    ConnectionApi,
    CredentialsApi,
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
    controller.anoncreds_revocation = Mock(spec=AnoncredsRevocationApi)
    controller.anoncreds_schemas = Mock(spec=AnoncredsSchemasApi)
    controller.connection = Mock(spec=ConnectionApi)
    controller.credentials = Mock(spec=CredentialsApi)
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
        self.controller = controller

    async def __aenter__(self):
        return self.controller

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def mock_agent_controller():
    return get_mock_agent_controller()


@pytest.fixture
def mock_context_managed_controller():
    return MockContextManagedController


@pytest.fixture(scope="session")
def mock_governance_auth() -> AcaPyAuthVerified:
    auth = Mock(spec=AcaPyAuthVerified)
    auth.role = Role.GOVERNANCE
    auth.token = GOVERNANCE_AGENT_API_KEY
    auth.wallet_id = GOVERNANCE_LABEL
    return auth


@pytest.fixture
def mock_admin_auth() -> AcaPyAuthVerified:
    auth = Mock(spec=AcaPyAuthVerified)
    auth.role = Role.TENANT_ADMIN
    auth.token = GOVERNANCE_AGENT_API_KEY
    auth.wallet_id = "admin"
    return auth


@pytest.fixture
def mock_tenant_auth() -> AcaPyAuth:
    auth = Mock(spec=AcaPyAuth)
    auth.role = Role.TENANT
    auth.token = "tenant.test_token"
    return auth


@pytest.fixture
def mock_tenant_auth_verified() -> AcaPyAuthVerified:
    auth = Mock(spec=AcaPyAuthVerified)
    auth.role = Role.TENANT
    auth.token = "tenant.test_token"
    auth.wallet_id = "tenant_wallet_id"
    return auth

import pytest
from aries_cloudcontroller import (
    AcaPyClient,
    AnoncredsRevocationApi,
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
from mockito import mock

from app.dependencies.auth import AcaPyAuth, AcaPyAuthVerified
from app.dependencies.role import Role
from shared.constants import GOVERNANCE_AGENT_API_KEY, GOVERNANCE_LABEL


async def noop():
    return None


def get_mock_agent_controller() -> AcaPyClient:
    controller = mock(AcaPyClient)
    controller.__aexit__ = noop
    controller.anoncreds_revocation = mock(AnoncredsRevocationApi)
    controller.connection = mock(ConnectionApi)
    controller.credentials = mock(CredentialsApi)
    controller.endorse_transaction = mock(EndorseTransactionApi)
    controller.issue_credential_v2_0 = mock(IssueCredentialV20Api)
    controller.ledger = mock(LedgerApi)
    controller.out_of_band = mock(OutOfBandApi)
    controller.present_proof_v2_0 = mock(PresentProofV20Api)
    controller.revocation = mock(RevocationApi)
    controller.schema = mock(SchemaApi)
    controller.wallet = mock(WalletApi)
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
def mock_governance_auth():
    auth = mock(AcaPyAuthVerified)
    auth.role = Role.GOVERNANCE
    auth.token = GOVERNANCE_AGENT_API_KEY
    auth.wallet_id = GOVERNANCE_LABEL
    return auth


@pytest.fixture
def mock_admin_auth() -> AcaPyAuthVerified:
    auth = mock(AcaPyAuthVerified)
    auth.role = Role.TENANT_ADMIN
    auth.token = GOVERNANCE_AGENT_API_KEY
    auth.wallet_id = "admin"
    return auth


@pytest.fixture
def mock_tenant_auth():
    auth = mock(AcaPyAuth)
    auth.role = Role.TENANT
    auth.token = "tenant.test_token"
    return auth

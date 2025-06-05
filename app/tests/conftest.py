import pytest

from app.tests.fixtures.dids import register_issuer_key_ed25519
from app.tests.fixtures.member_acapy_clients import (
    acme_acapy_client,
    alice_acapy_client,
    bob_acapy_client,
    faber_anoncreds_acapy_client,
    governance_acapy_client,
    meld_co_anoncreds_acapy_client,
    tenant_admin_acapy_client,
)
from app.tests.fixtures.member_async_clients import (
    acme_client,
    alice_member_client,
    bob_member_client,
    faber_anoncreds_client,
    governance_client,
    meld_co_anoncreds_client,
    mock_async_client,
    tenant_admin_client,
    trust_registry_client,
)
from app.tests.fixtures.member_connections import (
    acme_and_alice_connection,
    bob_and_alice_connection,
    faber_anoncreds_and_alice_connection,
    meld_co_anoncreds_and_alice_connection,
    test_mode,
)
from app.tests.fixtures.member_wallets import (
    acme_verifier,
    alice_tenant,
    bob_tenant,
    faber_anoncreds_issuer,
    meld_co_anoncreds_issuer_verifier,
)
from shared.util.mock_agent_controller import (
    mock_admin_auth,
    mock_agent_controller,
    mock_context_managed_controller,
    mock_governance_auth,
    mock_tenant_auth,
    mock_tenant_auth_verified,
)

__all__ = [
    "register_issuer_key_ed25519",
    "acme_acapy_client",
    "alice_acapy_client",
    "bob_acapy_client",
    "faber_anoncreds_acapy_client",
    "governance_acapy_client",
    "meld_co_anoncreds_acapy_client",
    "tenant_admin_acapy_client",
    "acme_client",
    "alice_member_client",
    "bob_member_client",
    "faber_anoncreds_client",
    "governance_client",
    "meld_co_anoncreds_client",
    "mock_async_client",
    "tenant_admin_client",
    "trust_registry_client",
    "acme_and_alice_connection",
    "bob_and_alice_connection",
    "faber_anoncreds_and_alice_connection",
    "meld_co_anoncreds_and_alice_connection",
    "test_mode",
    "acme_verifier",
    "alice_tenant",
    "bob_tenant",
    "faber_anoncreds_issuer",
    "meld_co_anoncreds_issuer_verifier",
    "mock_admin_auth",
    "mock_agent_controller",
    "mock_context_managed_controller",
    "mock_governance_auth",
    "mock_tenant_auth",
    "mock_tenant_auth_verified",
]

# Imports make pytest fixtures visible to tests within this module

# In pytest, conftest.py is a special file used to share fixtures, hooks, and other configurations
# among multiple test files. It's automatically discovered by pytest when tests are run, and the
# fixtures and hooks defined within it can be used in any test file within the same directory or subdirectories.

# Pytest fixtures are reusable components that can be shared across multiple tests.
# They can also help set up and tear down resources needed for the tests.
# `autouse` means that the fixture will be automatically used for all tests in the pytest session,
# so there is no need to explicitly include it in the test functions.


@pytest.fixture(scope="session")
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})

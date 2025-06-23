from unittest.mock import Mock, patch

import pytest
from aries_cloudcontroller import AcaPyClient

from app.models.verifier import RevocationStatus
from app.models.wallet import CredInfo, CredInfoList
from app.services.wallet.wallet_credential import add_revocation_info


@pytest.fixture
def sample_cred_info():
    # Create CredInfo and explicitly set all fields
    cred_info = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id="789",
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    # Force set the credential_id using model fields
    cred_info.__dict__["credential_id"] = "cred-123"
    return cred_info


@pytest.fixture
def sample_non_revocable_cred_info():
    # Create CredInfo and explicitly set all fields
    cred_info = CredInfo(
        rev_reg_id=None,
        cred_rev_id=None,
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    # Force set the credential_id using model fields
    cred_info.__dict__["credential_id"] = "cred-456"
    return cred_info


@pytest.fixture
def sample_cred_info_list(sample_cred_info):
    return CredInfoList(results=[sample_cred_info])


@pytest.fixture
def sample_non_revocable_cred_info_list(sample_non_revocable_cred_info):
    return CredInfoList(results=[sample_non_revocable_cred_info])


@pytest.fixture
def mock_agent_controller():
    controller = Mock(spec=AcaPyClient)
    controller.credentials = Mock()
    return controller


@pytest.mark.anyio
async def test_add_revocation_info_valid_credential(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
):
    """Test adding revocation info for a valid, non-revoked credential."""
    # Mock the revocation status response - ensure it has the revoked attribute
    rev_status_response = Mock()
    rev_status_response.revoked = False

    with (
        patch(
            "app.services.wallet.wallet_credential.handle_acapy_call",
            return_value=rev_status_response,
        ) as mock_handle_call,
        patch("app.services.wallet.wallet_credential.logger") as mock_logger,
    ):
        result = await add_revocation_info(
            cred_info_list=sample_cred_info_list,
            aries_controller=mock_agent_controller,
        )

        # Verify the call was made correctly
        mock_handle_call.assert_called_once_with(
            logger=mock_logger,
            acapy_call=mock_agent_controller.credentials.get_revocation_status,
            credential_id="cred-123",
        )

        # Verify the revocation status was set correctly
        assert result.results[0].revocation_status == RevocationStatus.ACTIVE


@pytest.mark.anyio
async def test_add_revocation_info_revoked_credential(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
):
    """Test adding revocation info for a revoked credential."""
    # Mock the revocation status response - ensure it has the revoked attribute
    rev_status_response = Mock()
    rev_status_response.revoked = True

    with patch(
        "app.services.wallet.wallet_credential.handle_acapy_call",
        return_value=rev_status_response,
    ):
        result = await add_revocation_info(
            cred_info_list=sample_cred_info_list,
            aries_controller=mock_agent_controller,
        )

        # Verify the revocation status was set correctly
        assert result.results[0].revocation_status == RevocationStatus.REVOKED


@pytest.mark.anyio
async def test_add_revocation_info_error_handling(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
):
    """Test error handling when fetching revocation status fails."""
    with (
        patch(
            "app.services.wallet.wallet_credential.handle_acapy_call",
            side_effect=Exception("Network error"),
        ) as mock_handle_call,
        patch("app.services.wallet.wallet_credential.logger") as mock_logger,
    ):
        result = await add_revocation_info(
            cred_info_list=sample_cred_info_list,
            aries_controller=mock_agent_controller,
        )

        # Verify error was logged
        mock_logger.error.assert_called_once_with(
            "Error fetching revocation status for {}: {}",
            "cred-123",
            mock_handle_call.side_effect,
        )

        # Verify the revocation status was set to CHECK_FAILED
        assert result.results[0].revocation_status == RevocationStatus.CHECK_FAILED


@pytest.mark.anyio
async def test_add_revocation_info_empty_list(
    mock_agent_controller: AcaPyClient,
):
    """Test add_revocation_info with empty credential list."""
    empty_list = CredInfoList(results=[])

    result = await add_revocation_info(
        cred_info_list=empty_list,
        aries_controller=mock_agent_controller,
    )

    assert result.results == []


@pytest.mark.anyio
async def test_add_revocation_info_none_results(
    mock_agent_controller: AcaPyClient,
):
    """Test add_revocation_info with None results."""
    none_results_list = CredInfoList(results=None)

    result = await add_revocation_info(
        cred_info_list=none_results_list,
        aries_controller=mock_agent_controller,
    )

    assert result.results is None


@pytest.mark.anyio
async def test_add_revocation_info_mixed_credentials(
    mock_agent_controller: AcaPyClient,
):
    """Test add_revocation_info with mixed revocable/non-revocable credentials."""
    revocable_cred = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id="789",
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    revocable_cred.__dict__["credential_id"] = "cred-123"

    non_revocable_cred = CredInfo(
        rev_reg_id=None,
        cred_rev_id=None,
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    non_revocable_cred.__dict__["credential_id"] = "cred-456"

    mixed_list = CredInfoList(results=[revocable_cred, non_revocable_cred])

    # Mock the revocation status response
    rev_status_response = Mock()
    rev_status_response.revoked = False

    with patch(
        "app.services.wallet.wallet_credential.handle_acapy_call",
        return_value=rev_status_response,
    ):
        result = await add_revocation_info(
            cred_info_list=mixed_list,
            aries_controller=mock_agent_controller,
        )

        # Only the revocable credential should have status updated
        assert result.results[0].revocation_status == RevocationStatus.ACTIVE
        assert result.results[1].revocation_status is None

from unittest.mock import Mock, patch

import pytest
from aries_cloudcontroller import AcaPyClient

from app.models.verifier import RevocationStatus
from app.models.wallet import CredInfo, CredInfoList
from app.services.wallet.wallet_credential import (
    add_revocation_info,
    check_non_revocable,
)


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


@pytest.mark.anyio
async def test_check_non_revocable_valid_credential(
    sample_non_revocable_cred_info_list: CredInfoList,
):
    """Test check_non_revocable with a non-revocable credential."""
    with patch("app.services.wallet.wallet_credential.logger") as mock_logger:
        result = await check_non_revocable(
            cred_info_list=sample_non_revocable_cred_info_list,
        )

        # Verify the revocation status was set correctly
        assert result.results[0].revocation_status is None

        # Verify debug log was called
        mock_logger.debug.assert_called_once_with(
            "Credential {} is non-revocable (no revocation registry or revocation ID)",
            "cred-456",
        )


@pytest.mark.anyio
async def test_check_non_revocable_revocable_credential(
    sample_cred_info_list: CredInfoList,
):
    """Test check_non_revocable with a revocable credential."""
    with patch("app.services.wallet.wallet_credential.logger") as mock_logger:
        result = await check_non_revocable(
            cred_info_list=sample_cred_info_list,
        )

        # Revocable credential should not have status changed
        assert result.results[0].revocation_status == RevocationStatus.NOT_CHECKED

        # Debug log should not be called
        mock_logger.debug.assert_not_called()


@pytest.mark.anyio
async def test_check_non_revocable_empty_list():
    """Test check_non_revocable with empty credential list."""
    empty_list = CredInfoList(results=[])

    result = await check_non_revocable(
        cred_info_list=empty_list,
    )

    assert result.results == []


@pytest.mark.anyio
async def test_check_non_revocable_none_results():
    """Test check_non_revocable with None results."""
    none_results_list = CredInfoList(results=None)

    result = await check_non_revocable(
        cred_info_list=none_results_list,
    )

    assert result.results is None


@pytest.mark.anyio
async def test_check_non_revocable_mixed_credentials():
    """Test check_non_revocable with mixed revocable/non-revocable credentials."""
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

    with patch("app.services.wallet.wallet_credential.logger") as mock_logger:
        result = await check_non_revocable(
            cred_info_list=mixed_list,
        )

        # Only the non-revocable credential should have status updated
        assert result.results[0].revocation_status == RevocationStatus.NOT_CHECKED
        assert result.results[1].revocation_status is None

        # Debug log should be called once for the non-revocable credential
        mock_logger.debug.assert_called_once_with(
            "Credential {} is non-revocable (no revocation registry or revocation ID)",
            "cred-456",
        )


@pytest.mark.anyio
async def test_check_non_revocable_partial_revocation_info():
    """Test check_non_revocable with credentials having partial revocation info."""
    # Credential with rev_reg_id but no cred_rev_id
    partial_cred_1 = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id=None,
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    partial_cred_1.__dict__["credential_id"] = "cred-123"

    # Credential with cred_rev_id but no rev_reg_id
    partial_cred_2 = CredInfo(
        rev_reg_id=None,
        cred_rev_id="789",
        revocation_status=RevocationStatus.NOT_CHECKED,
    )
    partial_cred_2.__dict__["credential_id"] = "cred-456"

    partial_list = CredInfoList(results=[partial_cred_1, partial_cred_2])

    with patch("app.services.wallet.wallet_credential.logger") as mock_logger:
        result = await check_non_revocable(
            cred_info_list=partial_list,
        )

        # Both should be marked as non-revocable since they don't have complete revocation info
        assert result.results[0].revocation_status is None
        assert result.results[1].revocation_status is None

        # Debug log should be called twice
        assert mock_logger.debug.call_count == 2

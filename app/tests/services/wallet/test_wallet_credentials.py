from logging import Logger
from unittest.mock import Mock, patch

import pytest
from aries_cloudcontroller import AcaPyClient

from app.models.verifier import Status
from app.models.wallet import CredInfo, CredInfoList
from app.services.wallet.wallet_credential import (
    add_revocation_info,
    check_non_revokable,
)


@pytest.fixture
def mock_logger():
    return Mock(spec=Logger)


@pytest.fixture
def sample_cred_info():
    # Create CredInfo and explicitly set all fields
    cred_info = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id="789",
        revocation_status=Status.NOT_CHECKED,
    )
    # Force set the credential_id using model fields
    cred_info.__dict__["credential_id"] = "cred-123"
    return cred_info


@pytest.fixture
def sample_non_revokable_cred_info():
    # Create CredInfo and explicitly set all fields
    cred_info = CredInfo(
        rev_reg_id=None,
        cred_rev_id=None,
        revocation_status=Status.NOT_CHECKED,
    )
    # Force set the credential_id using model fields
    cred_info.__dict__["credential_id"] = "cred-456"
    return cred_info


@pytest.fixture
def sample_cred_info_list(sample_cred_info):
    return CredInfoList(results=[sample_cred_info])


@pytest.fixture
def sample_non_revokable_cred_info_list(sample_non_revokable_cred_info):
    return CredInfoList(results=[sample_non_revokable_cred_info])


@pytest.fixture
def mock_agent_controller():
    controller = Mock(spec=AcaPyClient)
    controller.credentials = Mock()
    return controller


@pytest.mark.anyio
async def test_add_revocation_info_valid_credential(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
    mock_logger: Logger,
):
    """Test adding revocation info for a valid, non-revoked credential."""
    # Mock the revocation status response - ensure it has the revoked attribute
    rev_status_response = Mock()
    rev_status_response.revoked = False

    with patch(
        "app.services.wallet.wallet_credential.handle_acapy_call",
        return_value=rev_status_response,
    ) as mock_handle_call:
        result = await add_revocation_info(
            cred_info_list=sample_cred_info_list,
            aries_controller=mock_agent_controller,
            logger=mock_logger,
        )

        # Verify the call was made correctly
        mock_handle_call.assert_called_once_with(
            logger=mock_logger,
            acapy_call=mock_agent_controller.credentials.get_revocation_status,
            credential_id="cred-123",
        )

        # Verify the revocation status was set correctly
        assert result.results[0].revocation_status == Status.VALID


@pytest.mark.anyio
async def test_add_revocation_info_revoked_credential(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
    mock_logger: Logger,
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
            logger=mock_logger,
        )

        # Verify the revocation status was set correctly
        assert result.results[0].revocation_status == Status.REVOKED


@pytest.mark.anyio
async def test_add_revocation_info_error_handling(
    mock_agent_controller: AcaPyClient,
    sample_cred_info_list: CredInfoList,
    mock_logger: Logger,
):
    """Test error handling when fetching revocation status fails."""
    with patch(
        "app.services.wallet.wallet_credential.handle_acapy_call",
        side_effect=Exception("Network error"),
    ) as mock_handle_call:
        result = await add_revocation_info(
            cred_info_list=sample_cred_info_list,
            aries_controller=mock_agent_controller,
            logger=mock_logger,
        )

        # Verify error was logged
        mock_logger.error.assert_called_once_with(
            "Error fetching revocation status for {}: {}",
            "cred-123",
            mock_handle_call.side_effect,
        )

        # Verify the revocation status was set to CHECK_FAILED
        assert result.results[0].revocation_status == Status.CHECK_FAILED


@pytest.mark.anyio
async def test_add_revocation_info_empty_list(
    mock_agent_controller: AcaPyClient,
    mock_logger: Logger,
):
    """Test add_revocation_info with empty credential list."""
    empty_list = CredInfoList(results=[])

    result = await add_revocation_info(
        cred_info_list=empty_list,
        aries_controller=mock_agent_controller,
        logger=mock_logger,
    )

    assert result.results == []


@pytest.mark.anyio
async def test_add_revocation_info_none_results(
    mock_agent_controller: AcaPyClient,
    mock_logger: Logger,
):
    """Test add_revocation_info with None results."""
    none_results_list = CredInfoList(results=None)

    result = await add_revocation_info(
        cred_info_list=none_results_list,
        aries_controller=mock_agent_controller,
        logger=mock_logger,
    )

    assert result.results is None


@pytest.mark.anyio
async def test_add_revocation_info_mixed_credentials(
    mock_agent_controller: AcaPyClient,
    mock_logger: Logger,
):
    """Test add_revocation_info with mixed revokable/non-revokable credentials."""
    revokable_cred = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id="789",
        revocation_status=Status.NOT_CHECKED,
    )
    revokable_cred.__dict__["credential_id"] = "cred-123"

    non_revokable_cred = CredInfo(
        rev_reg_id=None,
        cred_rev_id=None,
        revocation_status=Status.NOT_CHECKED,
    )
    non_revokable_cred.__dict__["credential_id"] = "cred-456"

    mixed_list = CredInfoList(results=[revokable_cred, non_revokable_cred])

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
            logger=mock_logger,
        )

        # Only the revokable credential should have status updated
        assert result.results[0].revocation_status == Status.VALID
        assert result.results[1].revocation_status == Status.NOT_CHECKED


@pytest.mark.anyio
async def test_check_non_revokable_valid_credential(
    sample_non_revokable_cred_info_list: CredInfoList,
    mock_logger: Logger,
):
    """Test check_non_revokable with a non-revokable credential."""
    result = await check_non_revokable(
        cred_info_list=sample_non_revokable_cred_info_list,
        logger=mock_logger,
    )

    # Verify the revocation status was set correctly
    assert result.results[0].revocation_status == Status.NON_REVOKABLE

    # Verify debug log was called
    mock_logger.debug.assert_called_once_with(
        "Credential {} is non-revokable (no revocation registry or revocation ID)",
        "cred-456",
    )


@pytest.mark.anyio
async def test_check_non_revokable_revokable_credential(
    sample_cred_info_list: CredInfoList,
    mock_logger: Logger,
):
    """Test check_non_revokable with a revokable credential."""
    result = await check_non_revokable(
        cred_info_list=sample_cred_info_list,
        logger=mock_logger,
    )

    # Revokable credential should not have status changed
    assert result.results[0].revocation_status == Status.NOT_CHECKED

    # Debug log should not be called
    mock_logger.debug.assert_not_called()


@pytest.mark.anyio
async def test_check_non_revokable_empty_list(mock_logger: Logger):
    """Test check_non_revokable with empty credential list."""
    empty_list = CredInfoList(results=[])

    result = await check_non_revokable(
        cred_info_list=empty_list,
        logger=mock_logger,
    )

    assert result.results == []


@pytest.mark.anyio
async def test_check_non_revokable_none_results(mock_logger: Logger):
    """Test check_non_revokable with None results."""
    none_results_list = CredInfoList(results=None)

    result = await check_non_revokable(
        cred_info_list=none_results_list,
        logger=mock_logger,
    )

    assert result.results is None


@pytest.mark.anyio
async def test_check_non_revokable_mixed_credentials(mock_logger: Logger):
    """Test check_non_revokable with mixed revokable/non-revokable credentials."""
    revokable_cred = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id="789",
        revocation_status=Status.NOT_CHECKED,
    )
    revokable_cred.__dict__["credential_id"] = "cred-123"

    non_revokable_cred = CredInfo(
        rev_reg_id=None,
        cred_rev_id=None,
        revocation_status=Status.NOT_CHECKED,
    )
    non_revokable_cred.__dict__["credential_id"] = "cred-456"

    mixed_list = CredInfoList(results=[revokable_cred, non_revokable_cred])

    result = await check_non_revokable(
        cred_info_list=mixed_list,
        logger=mock_logger,
    )

    # Only the non-revokable credential should have status updated
    assert result.results[0].revocation_status == Status.NOT_CHECKED
    assert result.results[1].revocation_status == Status.NON_REVOKABLE

    # Debug log should be called once for the non-revokable credential
    mock_logger.debug.assert_called_once_with(
        "Credential {} is non-revokable (no revocation registry or revocation ID)",
        "cred-456",
    )


@pytest.mark.anyio
async def test_check_non_revokable_partial_revocation_info(mock_logger: Logger):
    """Test check_non_revokable with credentials having partial revocation info."""
    # Credential with rev_reg_id but no cred_rev_id
    partial_cred_1 = CredInfo(
        rev_reg_id="rev-reg-456",
        cred_rev_id=None,
        revocation_status=Status.NOT_CHECKED,
    )
    partial_cred_1.__dict__["credential_id"] = "cred-123"

    # Credential with cred_rev_id but no rev_reg_id
    partial_cred_2 = CredInfo(
        rev_reg_id=None,
        cred_rev_id="789",
        revocation_status=Status.NOT_CHECKED,
    )
    partial_cred_2.__dict__["credential_id"] = "cred-456"

    partial_list = CredInfoList(results=[partial_cred_1, partial_cred_2])

    result = await check_non_revokable(
        cred_info_list=partial_list,
        logger=mock_logger,
    )

    # Both should be marked as non-revokable since they don't have complete revocation info
    assert result.results[0].revocation_status == Status.NON_REVOKABLE
    assert result.results[1].revocation_status == Status.NON_REVOKABLE

    # Debug log should be called twice
    assert mock_logger.debug.call_count == 2

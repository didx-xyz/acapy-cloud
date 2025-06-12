from logging import Logger
from unittest.mock import AsyncMock, Mock

import pytest
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from pydantic import ValidationError

from app.exceptions.cloudapi_exception import CloudApiException
from app.exceptions.handle_acapy_call import handle_acapy_call

dummy_acapy_call = "dummy_acapy_call"


# pylint: disable=redefined-outer-name


# Mock logger to avoid actual logging during tests
@pytest.fixture
def mock_logger() -> Mock:
    return Mock(spec=Logger)


# Sample Async function to simulate ACA-Py call
@pytest.fixture
def acapy_call() -> AsyncMock:
    mock = AsyncMock()
    mock.__name__ = dummy_acapy_call
    return mock


@pytest.mark.anyio
async def test_handle_acapy_call_with_bad_request_exception(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = BadRequestException(reason="Bad Request", status=400)

    acapy_call.__name__ = dummy_acapy_call
    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Bad Request"
    mock_logger.info.assert_called_with(
        "Bad request for {}: {}", "dummy_acapy_call", "Bad Request"
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_unauthorized_exception(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = UnauthorizedException(reason="Unauthorized", status=401)

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unauthorized"
    mock_logger.info.assert_called_with(
        "Bad request for {}: {}", "dummy_acapy_call", "Unauthorized"
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_forbidden_exception(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = ForbiddenException(reason="Forbidden", status=403)

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Forbidden"
    mock_logger.info.assert_called_with(
        "Bad request for {}: {}", "dummy_acapy_call", "Forbidden"
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_not_found_exception(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = NotFoundException(reason="Not Found", status=404)

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Not Found"
    mock_logger.info.assert_called_with(
        "Bad request for {}: {}", "dummy_acapy_call", "Not Found"
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_validation_error(acapy_call, mock_logger) -> None:
    # Create a dummy ValidationError
    acapy_call.side_effect = ValidationError.from_exception_data(
        "Foo",
        [{"type": "greater_than", "loc": ("a", 2), "input": 4, "ctx": {"gt": 5}}],
    )

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 422
    assert "greater than" in exc_info.value.detail
    mock_logger.info.assert_called_with(
        "Bad request: Validation error during {}: {}",
        "dummy_acapy_call",
        exc_info.value.detail,
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_api_exception_422(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = ApiException(reason="Unprocessable Entity", status=422)

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Unprocessable Entity"
    mock_logger.info.assert_called_with(
        "Bad request: Validation error during {}: {}",
        "dummy_acapy_call",
        "Unprocessable Entity",
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_api_exception_500(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = ApiException(reason="Internal Server Error", status=500)

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal Server Error"
    mock_logger.warning.assert_called_with(
        "Error during {}: {}", "dummy_acapy_call", "Internal Server Error"
    )


@pytest.mark.anyio
async def test_handle_acapy_call_with_generic_exception(
    acapy_call, mock_logger
) -> None:
    acapy_call.side_effect = Exception("Something went wrong")

    with pytest.raises(CloudApiException) as exc_info:
        await handle_acapy_call(mock_logger, acapy_call)
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal server error"
    mock_logger.exception.assert_called_with("Unexpected exception from ACA-Py call")

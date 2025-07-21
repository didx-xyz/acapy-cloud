from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientConnectionResetError
from aries_cloudcontroller.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from pydantic import ValidationError

from app.exceptions.cloudapi_exception import CloudApiException
from app.util.extract_validation_error import extract_validation_error_msg
from shared.log_config import Logger


async def handle_acapy_call[T](
    logger: Logger, acapy_call: Callable[..., Coroutine[Any, Any, T]], *args, **kwargs
) -> T:
    """Executes an ACA-Py client call with standardized error handling.

    This function wraps ACA-Py client calls to catch and log exceptions in a standardized manner.
    It re-raises exceptions as CloudApiException for API error responses.

    Args:
        logger (Logger): The logger object for logging messages.
        acapy_call (Callable[..., Coroutine[Any, Any, T]]): The ACA-Py client call to execute.
        *args: Positional arguments to pass to the ACA-Py client call.
        **kwargs: Keyword arguments to pass to the ACA-Py client call.

    Returns:
        T: The result of the ACA-Py client call, of generic type T.

    Raises:
        CloudApiException: Custom API exception with status code and detail when API calls fail.

    """
    method_identifier = acapy_call.__name__
    try:
        return await acapy_call(*args, **kwargs)
    except (
        BadRequestException,
        UnauthorizedException,
        ForbiddenException,
        NotFoundException,
    ) as e:
        # Handle 400 errors:
        logger.info("Bad request for {}: {}", method_identifier, e.reason)
        raise CloudApiException(status_code=e.status, detail=e.reason) from e
    except ValidationError as e:
        # Handle Pydantic validation errors:
        error_msg = extract_validation_error_msg(e)
        logger.info(
            "Bad request: Validation error during {}: {}",
            method_identifier,
            error_msg,
        )
        raise CloudApiException(status_code=422, detail=error_msg) from e
    except ApiException as e:
        error_msg = e.reason
        status = e.status
        if status == 422:
            # handle 422 errors:
            logger.info(
                "Bad request: Validation error during {}: {}",
                method_identifier,
                error_msg,
            )
            raise CloudApiException(status_code=422, detail=error_msg) from e
        else:
            # Handle other / 500 errors:
            logger.warning("Error during {}: {}", method_identifier, error_msg)
            raise CloudApiException(status_code=status, detail=error_msg) from e
    except ClientConnectionResetError as e:
        logger.error("Client connection reset error")
        raise CloudApiException(
            status_code=500, detail="Client connection reset error"
        ) from e
    except Exception as e:
        # General exceptions:
        logger.exception("Unexpected exception from ACA-Py call")
        raise CloudApiException(status_code=500, detail="Internal server error") from e

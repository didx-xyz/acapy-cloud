import asyncio
from logging import Logger
from typing import Any, Callable, Coroutine, Optional, Tuple, TypeVar

T = TypeVar("T", bound=Any)


async def coroutine_with_retry(
    coroutine_func: Callable[..., Coroutine[Any, Any, T]],
    args: Tuple,
    logger: Logger,
    max_attempts=5,
    retry_delay=2,
) -> T:
    result = None
    for attempt in range(max_attempts):
        try:
            result = await coroutine_func(*args)
            break
        except Exception as e:
            if attempt + 1 == max_attempts:
                logger.error("Maximum number of retries exceeded. Failing.")
                raise e  # Re-raise the exception if max attempts exceeded

            logger.warning(
                (
                    "Failed to run coroutine (attempt {}). "
                    "Reason: \n{}.\n"
                    "Retrying in {} seconds..."
                ),
                attempt + 1,
                e,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
    return result


async def coroutine_with_retry_until_value(
    coroutine_func: Callable[..., Coroutine[Any, Any, T]],
    args: Tuple,
    field_name: Optional[str],
    expected_value: Any,
    logger: Logger,
    max_attempts: int = 5,
    retry_delay: int = 2,
) -> T:
    """
    Executes a coroutine function with retries until it returns an expected value
    or until a maximum number of attempts is reached.

    Args:
        coroutine_func (Callable): The coroutine function to be called. It should be awaitable.
        args (Tuple): The arguments to pass to the coroutine function.
        field_name (str): The name of the field in the returned object to check against the expected value.
        expected_value (Any): The value that the coroutine should return for the call to be considered successful.
        logger (Logger): Logger instance used to log information and warnings about the retry attempts and exceptions.
        max_attempts (int, optional): The maximum number of attempts to make. Defaults to 5.
        retry_delay (int, optional): The delay in seconds between attempts. Defaults to 2.

    Returns:
        Any: The result of the coroutine if it matches the expected value within the allowed number of attempts.
             Returns `None` if the maximum number of attempts is reached without achieving the expected result.

    Raises:
        Exception: Re-raises any exception encountered on the final attempt.
    """
    for attempt in range(max_attempts):
        try:
            result = await coroutine_func(*args)

            if field_name:
                if getattr(result, field_name, None) == expected_value:
                    return result
            else:
                if result == expected_value:
                    return result

            if attempt + 1 < max_attempts:
                logger.info(
                    (
                        "Coroutine returned {} instead of expected {} "
                        "(attempt {}). Retrying in {} seconds..."
                    ),
                    result,
                    expected_value,
                    attempt + 1,
                    retry_delay,
                )
            else:
                logger.error(
                    "Maximum number of retries exceeded without returning expected value."
                )
                raise asyncio.TimeoutError

        except Exception as e:
            if attempt + 1 == max_attempts:
                logger.error(
                    "Maximum number of retries exceeded with exception. Failing."
                )
                raise asyncio.TimeoutError from e  # Raise TimeoutError if max attempts exceeded

            logger.warning(
                (
                    "Exception encountered (attempt {}). "
                    "Reason: \n{}.\n"
                    "Retrying in {} seconds..."
                ),
                attempt + 1,
                e,
                retry_delay,
            )

        await asyncio.sleep(retry_delay)

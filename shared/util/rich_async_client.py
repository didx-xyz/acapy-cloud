import asyncio
import logging
import ssl

from fastapi import HTTPException
from httpx import AsyncClient, ConnectTimeout, HTTPStatusError, Response

logger = logging.getLogger(__name__)

ssl_context = ssl.create_default_context()


class RichAsyncClient(AsyncClient):
    """Async Client that extends httpx.AsyncClient with built-in error handling and SSL cert reuse.

    - Reuses SSL context for better performance
    - Retries requests on 502 Bad Gateway and 503 Service Unavailable errors
    - Raises HTTPException with detailed error messages

    Args:
        name (Optional[str]): Optional name for the client, prepended to exceptions.
        verify: SSL certificate verification context.
        raise_status_error (bool): Whether to raise an error for 4xx and 5xx status codes.
        retries (int): Number of retry attempts for failed requests.
        retry_on (List[int]): List of HTTP status codes that should trigger a retry.
        retry_wait_seconds (float): Number of seconds to wait before retrying.

    """

    def __init__(
        self,
        *args,
        name: str | None = None,
        verify: ssl.SSLContext = ssl_context,
        raise_status_error: bool = True,
        retries: int = 3,
        retry_on: list[int] | None = None,
        retry_wait_seconds: float = 0.5,
        **kwargs,
    ) -> None:
        """Initialize the rich async client."""
        super().__init__(*args, verify=verify, **kwargs)
        self.name = name + " - HTTP" if name else "HTTP"  # prepended to exceptions
        self.raise_status_error = raise_status_error
        self.retries = retries
        self.retry_on = retry_on if retry_on is not None else [502, 503]
        self.retry_wait_seconds = retry_wait_seconds

    async def _handle_response(self, response: Response) -> Response:
        if self.raise_status_error:
            response.raise_for_status()  # Raise exception for 4xx and 5xx status codes
        return response

    async def _handle_error(self, e: HTTPStatusError, url: str, method: str) -> None:
        code = e.response.status_code
        message = e.response.text
        log_message = (
            f"{self.name} {method} `{url}` failed. "
            f"Status code: {code}. Response: `{message}`."
        )
        logger.error(log_message)
        raise HTTPException(status_code=code, detail=message) from e

    async def _request_with_retries(self, method: str, url: str, **kwargs) -> Response:
        for attempt in range(self.retries):
            try:
                response = await getattr(super(), method)(url, **kwargs)
                return await self._handle_response(response)
            except (HTTPStatusError, ConnectTimeout) as e:
                if isinstance(e, HTTPStatusError):
                    code = e.response.status_code
                    if code not in self.retry_on or attempt >= self.retries - 1:
                        await self._handle_error(e, url, method)
                    error_msg = f"failed with status code {code}"
                else:
                    error_msg = "failed with httpx.ConnectTimeout"

                log_message = (
                    f"{self.name} {method} `{url}` {error_msg}. "
                    f"Retrying attempt {attempt + 1}/{self.retries}."
                )
                logger.warning(log_message)
                await asyncio.sleep(self.retry_wait_seconds)  # Wait before retrying
                continue  # Retry the request

    async def post(self, url: str, **kwargs) -> Response:
        return await self._request_with_retries("post", url, **kwargs)

    async def get(self, url: str, **kwargs) -> Response:
        return await self._request_with_retries("get", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> Response:
        return await self._request_with_retries("delete", url, **kwargs)

    async def put(self, url: str, **kwargs) -> Response:
        return await self._request_with_retries("put", url, **kwargs)

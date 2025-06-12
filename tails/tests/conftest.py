import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> tuple[str, dict[str, bool]]:
    return ("asyncio", {"use_uvloop": True})

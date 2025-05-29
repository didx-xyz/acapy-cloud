import pytest

@pytest.fixture(scope="session")
def anyio_backend():
    return ("asyncio", {"use_uvloop": True})

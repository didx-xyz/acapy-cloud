from contextlib import asynccontextmanager

import dependencies
import pytest
from aries_cloudcontroller import (
    AcaPyClient,
)
from assertpy import assert_that
from fastapi import APIRouter, Depends, HTTPException
from httpx import AsyncClient
from main import app


TEST_BEARER_HEADER = "Bearer x"
TEST_BEARER_HEADER_2 = "Bearer Y"
BEARER_TOKEN = "Bearer 12345"


def test_extract_token_from_bearer():
    # assert_that(yoma_agent).is_type_of(AcaPyClient)
    assert_that(
        dependencies._extract_jwt_token_from_security_header("Bearer TOKEN")
    ).is_equal_to("TOKEN")


@pytest.mark.asyncio
async def test_yoma_agent():
    async with asynccontextmanager(dependencies.yoma_agent)(
        x_api_key="adminApiKey"
    ) as c:
        assert c is not None
        assert c.client.headers["x-api-key"] == "adminApiKey"

    with pytest.raises(HTTPException):
        async with asynccontextmanager(dependencies.yoma_agent)() as c:
            assert c is None


@pytest.mark.asyncio
async def test_ecosystem_agent():
    async with asynccontextmanager(dependencies.ecosystem_agent)(
        x_api_key="adminApiKey", x_auth=BEARER_TOKEN
    ) as c:
        assert c is not None
        assert c.client.headers["authorization"] == BEARER_TOKEN

    with pytest.raises(HTTPException):
        async with asynccontextmanager(dependencies.ecosystem_agent)() as c:
            assert c is None


@pytest.mark.asyncio
async def test_member_agent():
    async with asynccontextmanager(dependencies.member_agent)(x_auth=BEARER_TOKEN) as c:
        assert c is not None
        assert c.client.headers["authorization"] == BEARER_TOKEN

    with pytest.raises(HTTPException):
        async with asynccontextmanager(dependencies.member_agent)() as c:
            assert c is None


@pytest.mark.asyncio
async def test_member_admin_agent():
    async with asynccontextmanager(dependencies.member_admin_agent)(
        x_api_key="adminApiKey"
    ) as c:
        assert c is not None
        assert c.client.headers["x-api-key"] == "adminApiKey"
        assert c.multitenancy is not None

    with pytest.raises(HTTPException):
        async with asynccontextmanager(dependencies.member_admin_agent)() as c:
            assert c is None


async def async_next(param):
    async for item in param:
        return item
    else:  # NOSONAR
        return None


@pytest.fixture
def setup_agent_urls_for_testing():
    # fixture overrides the default config values
    # this is important as the default config values (as they are at the point of writing this code) have
    # an equal value in the member agent url and the eco system agent url so tests cannot correctly validate
    # the correct value is being used. This fixture ensures they are unique.
    ecosystem_agent_url = dependencies.ECOSYSTEM_AGENT_URL
    member_agent_url = dependencies.MEMBER_AGENT_URL
    yoma_agent_url = dependencies.YOMA_AGENT_URL
    embedded_api_key = dependencies.EMBEDDED_API_KEY
    dependencies.ECOSYSTEM_AGENT_URL = "ecosystem-agent-url"
    dependencies.MEMBER_AGENT_URL = "member-agent-url"
    dependencies.YOMA_AGENT_URL = "yoma-agent-url"
    dependencies.EMBEDDED_API_KEY = "test-embedded-api-key"
    yield
    dependencies.ECOSYSTEM_AGENT_URL = ecosystem_agent_url
    dependencies.MEMBER_AGENT_URL = member_agent_url
    dependencies.YOMA_AGENT_URL = yoma_agent_url
    dependencies.EMBEDDED_API_KEY = embedded_api_key


agent_selector_data = [
    (dependencies.agent_selector, False, AcaPyClient),
    (dependencies.admin_agent_selector, True, AcaPyClient),
]


@pytest.mark.parametrize(
    "dependency_function, is_multitenant, controller_type", agent_selector_data
)
@pytest.mark.asyncio
async def test_agent_selector(
    dependency_function, is_multitenant, controller_type, setup_agent_urls_for_testing
):
    # apologies fro the use of async_next... maybe we should just add the async context manager to these methods
    # even though fastapi does that for us. I'd assume it will play nice if they are already there.
    # then we can at least have a consistency of calling pattern. tests can use as is. WE don't have to wrap.
    # maybe create another ticket to look at this.
    with pytest.raises(HTTPException) as e:
        await async_next(
            dependency_function(x_api_key="apikey", x_auth=TEST_BEARER_HEADER)
        )
    assert e.value.status_code == 400
    assert e.value.detail == "invalid role"

    c = await async_next(
        dependency_function(
            x_api_key="apikey", x_auth=TEST_BEARER_HEADER, x_role="ecosystem"
        )
    )
    assert isinstance(c, controller_type)
    assert c.base_url == "ecosystem-agent-url"

    c = await async_next(
        dependency_function(
            x_api_key="apikey", x_auth=TEST_BEARER_HEADER, x_role="member"
        )
    )
    assert isinstance(c, controller_type)
    assert c.base_url == "member-agent-url"

    c = await async_next(
        dependency_function(
            x_api_key="apikey", x_auth=TEST_BEARER_HEADER, x_role="yoma"
        )
    )
    assert isinstance(c, AcaPyClient)
    assert c.base_url == "yoma-agent-url"


@pytest.mark.asyncio
async def test_web_ecosystem_or_member(setup_agent_urls_for_testing):
    # Test adds two methods to the router it creates (/testabc) - called this to make
    # sure it doesn't interfere with normal operation
    # this method then saves the injected agent and then the test validates the injected
    # agent is injected as it expects.

    # a parameterised test might be a better way to go - I'm not sure. Parameterised tests can be quite opaque
    # sometimes

    router = APIRouter(prefix="/testsabc")

    injected_controller = None

    @router.get("/admin")
    async def call_admin(
        aries_controller: AcaPyClient = Depends(dependencies.admin_agent_selector),
    ):
        nonlocal injected_controller
        injected_controller = aries_controller

    @router.get("/")
    async def call(
        aries_controller: AcaPyClient = Depends(dependencies.agent_selector),
    ):
        nonlocal injected_controller
        injected_controller = aries_controller

    app.include_router(router)

    async def make_call(route_suffix="", headers=None):
        async with AsyncClient(app=app, base_url="http://localhost:8000") as ac:
            response = await ac.get("/testsabc" + route_suffix, headers={**headers})
            return response

    # default (non admin) agents
    # when
    response = await make_call(headers={})
    # then
    assert response.status_code == 422
    assert (
        response.text
        == '{"detail":[{"loc":["header","x-role"],"msg":"field required","type":"value_error.missing"}]}'
    )

    # when
    await make_call(
        headers={
            "x-role": "yoma",
            "x-api-key": "ADDASDFDFF",
        }
    )
    # then
    assert injected_controller.base_url == dependencies.YOMA_AGENT_URL
    assert injected_controller.client.headers["x-api-key"] == "ADDASDFDFF"
    assert isinstance(injected_controller, AcaPyClient)

    # when
    await make_call(headers={"x-role": "ecosystem", "x-auth": TEST_BEARER_HEADER})
    # then
    assert injected_controller.base_url == dependencies.ECOSYSTEM_AGENT_URL
    assert injected_controller.client.headers["authorization"] == TEST_BEARER_HEADER
    assert (
        injected_controller.client.headers["x-api-key"] == dependencies.EMBEDDED_API_KEY
    )
    assert isinstance(injected_controller, AcaPyClient)

    # when
    await make_call(headers={"x-role": "member", "x-auth": TEST_BEARER_HEADER_2})
    # then
    assert injected_controller.base_url == dependencies.MEMBER_AGENT_URL
    assert injected_controller.client.headers["authorization"] == TEST_BEARER_HEADER_2
    assert (
        injected_controller.client.headers["x-api-key"] == dependencies.EMBEDDED_API_KEY
    )
    assert isinstance(injected_controller, AcaPyClient)

    # admin agents
    # when
    response = await make_call(headers={}, route_suffix="/admin")
    # then
    assert response.status_code == 422
    assert (
        response.text
        == '{"detail":[{"loc":["header","x-role"],"msg":"field required","type":"value_error.missing"}]}'
    )
    # when
    await make_call(
        route_suffix="/admin",
        headers={
            "x-role": "yoma",
            "x-api-key": "ADDASDFDFF",
        },
    )
    # then
    assert injected_controller.base_url == dependencies.YOMA_AGENT_URL
    assert injected_controller.client.headers["x-api-key"] == "ADDASDFDFF"
    assert isinstance(injected_controller, AcaPyClient)

    # when
    await make_call(
        route_suffix="/admin",
        headers={
            "x-api-key": "provided-api-key",
            "x-role": "ecosystem",
            "x-auth": TEST_BEARER_HEADER,
        },
    )
    # then
    assert injected_controller.base_url == dependencies.ECOSYSTEM_AGENT_URL
    assert injected_controller.client.headers["x-api-key"] == "provided-api-key"
    assert isinstance(injected_controller, AcaPyClient)

    # when
    await make_call(
        route_suffix="/admin",
        headers={
            "x-api-key": "provided-x-api-key-1",
            "x-role": "member",
            "x-auth": TEST_BEARER_HEADER_2,
        },
    )
    # then
    assert injected_controller.base_url == dependencies.MEMBER_AGENT_URL
    assert injected_controller.client.headers["x-api-key"] == "provided-x-api-key-1"
    assert isinstance(injected_controller, AcaPyClient)


@pytest.mark.asyncio
async def test_ecosystem_admin_agent():
    async with asynccontextmanager(dependencies.ecosystem_admin_agent)(
        x_api_key="adminApiKey"
    ) as c:
        assert c is not None
        assert c.client.headers["x-api-key"] == "adminApiKey"
        assert c.multitenancy is not None

    with pytest.raises(HTTPException):
        async with asynccontextmanager(dependencies.ecosystem_admin_agent)() as c:
            assert c is None

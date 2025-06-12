from unittest.mock import MagicMock, Mock, patch

import pydantic
import pytest
from aries_cloudcontroller import ApiException
from fastapi import HTTPException, Request
from fastapi.responses import ORJSONResponse

from app.exceptions.cloudapi_exception import CloudApiException
from app.main import (
    OPENAPI_NAME,
    acapy_cloud_description,
    acapy_cloud_docs_description,
    app,
    create_app,
    default_docs_description,
    read_openapi_yaml,
    routes_for_role,
    tenant_admin_routes,
    tenant_routes,
    trust_registry_routes,
    universal_exception_handler,
)
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_create_app():
    with patch("os.getenv") as mock_getenv:
        mock_getenv.return_value = "False"  # Mock the 'prod' environment variable
        created_app = create_app()
        assert created_app.title == OPENAPI_NAME

        # Verifying that all routes are included
        routes = [route.path for route in created_app.routes]
        expected_routes = ["/openapi.json", "/v1/tenants"]
        for route in expected_routes:
            assert route in routes


@pytest.mark.parametrize(
    "role, expected",
    [
        ("governance", tenant_routes),
        ("tenant", tenant_routes),
        ("tenant-admin", tenant_admin_routes),
        ("public", trust_registry_routes),
        ("*", set(tenant_admin_routes + tenant_routes + trust_registry_routes)),
        ("unknown", []),
    ],
)
def test_routes_for_role(role, expected):
    assert routes_for_role(role) == expected


@pytest.mark.parametrize(
    "role, expected",
    [
        ("governance", acapy_cloud_docs_description),
        ("tenant", acapy_cloud_docs_description),
        ("tenant-admin", acapy_cloud_docs_description),
        ("*", acapy_cloud_docs_description),
        ("public", default_docs_description),
        ("unknown", default_docs_description),
    ],
)
def test_description_for_roles(role, expected):
    assert acapy_cloud_description(role) == expected


def test_read_openapi_yaml():
    # Mock the openapi() function to return a sample openapi dictionary
    app.openapi = MagicMock(
        return_value={
            "openapi": "3.0.0",
            "info": {"title": "Sample API", "version": "1.0"},
        }
    )
    # Call the endpoint function
    response = read_openapi_yaml()

    expected_output = b"openapi: 3.0.0\ninfo:\n  title: Sample API\n  version: '1.0'\n"
    # Check that the response content is as expected
    assert response.body == expected_output
    assert response.media_type == "text/yaml"


@pytest.mark.anyio
async def test_universal_exception_handler():
    dummy_validation_error = pydantic.ValidationError.from_exception_data(
        "Foo",
        [{"type": "greater_than", "loc": ("a", 2), "input": 4, "ctx": {"gt": 5}}],
    )
    test_cases = [
        (
            CloudApiException(detail="Cloud API error", status_code=400),
            400,
            "Cloud API error",
        ),
        (ApiException(reason="API error", status=401), 401, "API error"),
        (
            HTTPException(status_code=404, detail="Not found", headers={}),
            404,
            "Not found",
        ),
        (CloudApiValueError(detail="Value error"), 422, "Value error"),
        (dummy_validation_error, 422, ""),
        (Exception("Unknown error"), 500, "Internal server error"),
    ]

    for exception, expected_status, expected_detail in test_cases:
        request = Mock(spec=Request)
        response = await universal_exception_handler(request, exception)
        assert isinstance(response, ORJSONResponse)
        assert response.status_code == expected_status
        assert expected_detail in response.body.decode()

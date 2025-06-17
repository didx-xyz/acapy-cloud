import io
import os
import traceback

import pydantic
import yaml
from aries_cloudcontroller import ApiException
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, ORJSONResponse
from scalar_fastapi import get_scalar_api_reference

from app.exceptions import CloudApiException
from app.routes import (
    connections,
    definitions,
    issuer,
    jsonld,
    messaging,
    oob,
    revocation,
    sse,
    trust_registry,
    verifier,
)
from app.routes.admin import tenants
from app.routes.wallet import credentials as wallet_credentials
from app.routes.wallet import dids as wallet_dids
from app.routes.wallet import jws as wallet_jws
from app.routes.wallet import sd_jws as wallet_sd_jws
from app.util.extract_validation_error import extract_validation_error_msg
from shared.constants import PROJECT_VERSION
from shared.exceptions import CloudApiValueError
from shared.log_config import get_logger
from shared.util.set_event_loop_policy import set_event_loop_policy

set_event_loop_policy()

OPENAPI_NAME = os.getenv("OPENAPI_NAME", "acapy-cloud")
ROLE = os.getenv("ROLE", "*")
ROOT_PATH = os.getenv("ROOT_PATH", "")

acapy_cloud_docs_description = f"""
Welcome to {OPENAPI_NAME}!

For detailed guidance on using the API, please visit our official documentation:
https://www.didx.co.za/acapy-cloud/index.html
"""

default_docs_description = f"""
Welcome to {OPENAPI_NAME}!
"""

logger = get_logger(__name__)
prod = os.environ.get("prod", "true").upper() == "TRUE"
debug = not prod

trust_registry_routes = [trust_registry]
tenant_admin_routes = [tenants, sse]
tenant_routes = [
    connections,
    definitions,
    issuer,
    revocation,
    jsonld,
    messaging,
    oob,
    verifier,
    wallet_credentials,
    wallet_dids,
    wallet_jws,
    wallet_sd_jws,
    sse,
]


def routes_for_role(role: str) -> list:
    if role in ("governance", "tenant"):
        return tenant_routes
    elif role == "tenant-admin":
        return tenant_admin_routes
    elif role == "public":
        return trust_registry_routes
    elif role == "*":
        return list(set(tenant_admin_routes + tenant_routes + trust_registry_routes))
    else:
        return []


def acapy_cloud_description(role: str) -> str:
    if role in ("governance", "tenant", "tenant-admin", "*"):
        return acapy_cloud_docs_description
    else:
        return default_docs_description


def create_app() -> FastAPI:
    application = FastAPI(
        root_path=ROOT_PATH,
        title=OPENAPI_NAME,
        version=PROJECT_VERSION,
        description=acapy_cloud_description(ROLE),
        debug=debug,
        redoc_url=None,
        docs_url=None,
    )

    for route in routes_for_role(ROLE):
        # Routes will appear in the openapi docs with the same order as defined in `routes`
        application.include_router(route.router)

    return application


app = create_app()


# Use Scalar instead of Swagger
@app.get("/docs", include_in_schema=False)
async def scalar_html() -> HTMLResponse:
    openapi_url = (
        os.path.join(ROOT_PATH, app.openapi_url.lstrip("/"))
        if app.openapi_url
        else None
    )
    return get_scalar_api_reference(
        openapi_url=openapi_url,
        title=app.title,
        servers=[{"url": ROOT_PATH} if ROOT_PATH else {}],
    )


# additional yaml version of openapi.json
@app.get("/openapi.yaml", include_in_schema=False)
def read_openapi_yaml() -> Response:
    logger.debug("GET request received: OpenAPI yaml endpoint")
    openapi_json = app.openapi()
    yaml_s = io.StringIO()
    yaml.dump(openapi_json, yaml_s, allow_unicode=True, sort_keys=False)
    logger.debug("Returning OpenAPI yaml text.")
    return Response(content=yaml_s.getvalue(), media_type="text/yaml")


@app.exception_handler(Exception)
async def universal_exception_handler(
    _: Request, exception: Exception
) -> ORJSONResponse:
    stacktrace = {"traceback": traceback.format_exc()} if debug else {}

    if isinstance(exception, CloudApiException):
        return ORJSONResponse(
            content={"detail": exception.detail, **stacktrace},
            status_code=exception.status_code,
        )

    if isinstance(exception, CloudApiValueError):
        return ORJSONResponse(
            {"detail": exception.detail, **stacktrace},
            status_code=422,
        )

    if isinstance(exception, pydantic.ValidationError):
        return ORJSONResponse(
            {"detail": extract_validation_error_msg(exception), **stacktrace},
            status_code=422,
        )

    if isinstance(exception, ApiException):
        return ORJSONResponse(
            {"detail": exception.reason, **stacktrace},
            status_code=exception.status,
        )

    if isinstance(exception, HTTPException):
        return ORJSONResponse(
            {"detail": exception.detail, **stacktrace},
            status_code=exception.status_code,
            headers=exception.headers,
        )

    return ORJSONResponse(
        {"detail": "Internal server error", "exception": str(exception), **stacktrace},
        status_code=500,
    )

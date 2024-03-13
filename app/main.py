import io
import os
import traceback
from contextlib import asynccontextmanager

import pydantic
import yaml
from aiohttp import ClientResponseError
from aries_cloudcontroller import ApiException
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.exceptions import CloudApiException
from app.routes import (
    connections,
    definitions,
    issuer,
    jsonld,
    messaging,
    oob,
    sse,
    trust_registry,
    verifier,
    webhooks,
    websocket_endpoint,
)
from app.routes.admin import tenants
from app.routes.wallet import credentials as wallet_credentials
from app.routes.wallet import dids as wallet_dids
from app.routes.wallet import jws as wallet_jws
from app.routes.wallet import sd_jws as wallet_sd_jws
from app.services.event_handling.websocket_manager import WebsocketManager
from shared.log_config import get_logger

OPENAPI_NAME = os.getenv("OPENAPI_NAME", "OpenAPI")
PROJECT_VERSION = os.getenv("PROJECT_VERSION", "0.11.0")
ROLE = os.getenv("ROLE", "*")
ROOT_PATH = os.getenv("ROOT_PATH", "")

cloud_api_docs_description = """
Welcome to the Aries CloudAPI Python project.

In addition to the traditional HTTP-based endpoints described below, we also offer WebSocket endpoints for real-time interfacing with webhook events.

WebSocket endpoints are authenticated. This means that only users with valid authentication tokens can establish a WebSocket connection, and they can only subscribe to their own wallet's events. However, Admin users have the ability to subscribe by topic, or to any wallet.

Our WebSocket endpoints are as follows:

1. `/v1/ws/topic/{topic}`: (Admin only) This endpoint allows admins to receive all webhook events on a specific topic (e.g. `connections`, `credentials`, `proofs`, `endorsements`).

2. `/v1/ws/{wallet_id}`: This endpoint allows authenticated users to receive webhook events associated with a specific wallet ID.

3. `/v1/ws/{wallet_id}/{topic}`: Similar to above, but with topic-specific subscription.

For authentication, the WebSocket headers should include `x-api-key`: `<your key>`.

Please refer to our API documentation for more details about our authentication mechanism, as well as for information about the available topics.
"""

default_docs_description = """
Welcome to the Aries CloudAPI Python project.
"""

logger = get_logger(__name__)
prod = os.environ.get("prod", "true").upper() == "TRUE"
debug = not prod


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup logic occurs before yield
    yield
    # Shutdown logic occurs after yield
    logger.info("Calling WebsocketManager shutdown")
    await WebsocketManager.disconnect_all()


webhook_routes = [webhooks, sse, websocket_endpoint]

trust_registry_routes = [trust_registry]
tenant_admin_routes = [tenants] + webhook_routes
tenant_routes = [
    connections,
    definitions,
    issuer,
    jsonld,
    messaging,
    oob,
    verifier,
    wallet_credentials,
    wallet_dids,
    wallet_jws,
    wallet_sd_jws,
] + webhook_routes


def routes_for_role(role: str) -> list:
    if role in ("governance", "tenant"):
        return tenant_routes
    elif ROLE == "tenant-admin":
        return tenant_admin_routes
    elif ROLE == "public":
        return trust_registry_routes
    elif ROLE == "*":
        return tenant_admin_routes + tenant_routes + trust_registry_routes
    else:
        return []


def cloud_api_description(role: str) -> str:
    if role in ("governance", "tenant", "*"):
        return cloud_api_docs_description
    else:
        return default_docs_description


def create_app() -> FastAPI:
    application = FastAPI(
        root_path=ROOT_PATH,
        title=OPENAPI_NAME,
        version=PROJECT_VERSION,
        description=cloud_api_description(ROLE),
        lifespan=lifespan,
        debug=debug,
    )

    for route in routes_for_role(ROLE):
        # Routes will appear in the openapi docs with the same order as defined in `routes`
        application.include_router(route.router)

    return application


app = create_app()


# additional yaml version of openapi.json
@app.get("/openapi.yaml", include_in_schema=False)
def read_openapi_yaml() -> Response:
    logger.info("GET request received: OpenAPI yaml endpoint")
    openapi_json = app.openapi()
    yaml_s = io.StringIO()
    yaml.dump(openapi_json, yaml_s, allow_unicode=True, sort_keys=False)
    logger.info("Returning OpenAPI yaml text.")
    return Response(content=yaml_s.getvalue(), media_type="text/yaml")


@app.exception_handler(Exception)
async def client_response_error_exception_handler(
    request: Request, exception: Exception
):
    stacktrace = {"stack": traceback.format_exc()}

    if isinstance(exception, ClientResponseError):
        return JSONResponse(
            {"detail": exception.message, **(stacktrace if debug else {})},
            exception.status or 500,
        )

    if isinstance(exception, CloudApiException):
        return JSONResponse(
            {"detail": exception.detail, **(stacktrace if debug else {})},
            exception.status_code,
        )

    if isinstance(exception, ApiException):
        return JSONResponse(
            {"detail": exception.reason, **(stacktrace if debug else {})},
            exception.status,
        )

    if isinstance(exception, HTTPException):
        return JSONResponse(
            {**exception.detail, **(stacktrace if debug else {})},
            exception.status_code,
            exception.headers,
        )

    if isinstance(exception, pydantic.ValidationError):
        return JSONResponse({"detail": exception.errors()}, status_code=422)

    return JSONResponse(
        {"detail": "Internal server error", "exception": str(exception)}, 500
    )

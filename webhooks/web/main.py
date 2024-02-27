import os

from fastapi import FastAPI

from shared.log_config import get_logger
from webhooks.services import acapy_events_processor, sse_manager
from webhooks.services.dependency_injection.container import get_container
from webhooks.web.routers import sse, webhooks, websocket

logger = get_logger(__name__)


def create_app() -> FastAPI:
    container = get_container()
    container.wire(
        modules=[__name__, acapy_events_processor, sse, sse_manager, webhooks]
    )

    OPENAPI_NAME = os.getenv(
        "OPENAPI_NAME", "Aries Cloud API: Webhooks and Server-Sent Events"
    )
    PROJECT_VERSION = os.getenv("PROJECT_VERSION", "0.11.0")

    application = FastAPI(
        title=OPENAPI_NAME,
        description="""
        Welcome to the OpenAPI interface for the Aries Cloud API Webhooks and Server-Sent Events (SSE).
        This API enables the management and processing of webhook events generated by ACA-Py instances.
        It supports filtering and forwarding events to subscribers based on topic and wallet ID,
        as well as handling Server-Sent Events (SSE) for real-time communication with clients.
        """,
        version=PROJECT_VERSION,
    )

    application.include_router(webhooks.router)
    application.include_router(sse.router)
    application.include_router(websocket.router)

    return application


logger.info("Start webhooks server")
app = create_app()

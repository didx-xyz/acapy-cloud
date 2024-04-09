import os
from contextlib import asynccontextmanager

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, FastAPI, HTTPException

from shared.log_config import get_logger
from webhooks.services.acapy_events_processor import AcaPyEventsProcessor
from webhooks.services.dependency_injection.container import Container
from webhooks.services.sse_manager import SseManager
from webhooks.web.routers import sse, webhooks, websocket

logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    logger.info("Webhooks Service startup")

    # Initialize the container
    container = Container()
    container.wire(modules=[__name__, sse, webhooks])

    # Start singleton services
    container.redis_service()
    sse_manager = container.sse_manager()
    events_processor = container.acapy_events_processor()

    sse_manager.start()
    events_processor.start()  # should start after SSE Manager is listening
    yield

    logger.info("Shutting down Webhooks services...")
    await events_processor.stop()
    await sse_manager.stop()
    container.shutdown_resources()  # shutdown redis instance
    logger.info("Shut down Webhooks services.")


def create_app() -> FastAPI:
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
        lifespan=app_lifespan,
    )

    application.include_router(webhooks.router)
    application.include_router(sse.router)
    application.include_router(websocket.router)

    return application


logger.info("Start webhooks server")
app = create_app()


@app.get("/health")
@inject
async def health_check(
    acapy_events_processor: AcaPyEventsProcessor = Depends(
        Provide[Container.acapy_events_processor]
    ),
    sse_manager: SseManager = Depends(Provide[Container.sse_manager]),
):
    if acapy_events_processor.are_tasks_running() and sse_manager.are_tasks_running():
        return {"status": "healthy"}
    else:
        raise HTTPException(
            status_code=503, detail="One or more background tasks are not running."
        )

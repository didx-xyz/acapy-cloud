import asyncio
import os
from contextlib import asynccontextmanager

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, FastAPI, HTTPException

from shared.constants import PROJECT_VERSION
from shared.log_config import get_logger
from waypoint.routers import sse
from waypoint.services.dependency_injection.container import Container
from waypoint.services.nats_service import NatsEventsProcessor

logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    logger.info("Waypoint Service startup")

    container = Container()
    await container.init_resources()

    container.wire(modules=[__name__, sse])

    await container.nats_events_processor()

    yield

    logger.debug("Shutting down Waypoint service...")
    await container.shutdown_resources()
    logger.info("Waypoint Service shutdown")


def create_app() -> FastAPI:
    openapi_name = os.getenv("OPENAPI_NAME", "Waypoint Service")

    application = FastAPI(
        title=openapi_name,
        description="""
        Welcome to the OpenAPI interface for the Waypoint Service.
        The Waypoint Service enables the ability to wait for a specific event to occur before continuing.
        """,
        version=PROJECT_VERSION,
        lifespan=app_lifespan,
    )

    application.include_router(sse.router)

    return application


logger.info("Waypoint Service startup")

app = create_app()


@app.get("/health/live")
async def health_live():
    return {"status": "live"}


@app.get("/health/ready")
@inject
async def health_ready(
    nats_processor: NatsEventsProcessor = Depends(
        Provide[Container.nats_events_processor]
    ),
):
    try:
        jetstream_status = await asyncio.wait_for(
            nats_processor.check_jetstream(), timeout=5.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "error": "JetStream health check timed out"},
        )
    except Exception as e:  # pylint: disable=W0718
        raise HTTPException(
            status_code=500, detail={"status": "error", "error": str(e)}
        )

    if jetstream_status["is_working"]:
        return {"status": "ready", "jetstream": jetstream_status}
    else:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "jetstream": "JetStream not ready"},
        )

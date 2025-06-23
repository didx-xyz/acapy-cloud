import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from revocation_service.services.dependency_injection.container import Container
from shared.constants import PROJECT_VERSION
from shared.log_config import get_logger
from shared.util.set_event_loop_policy import set_event_loop_policy

set_event_loop_policy()

logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Revocation Service startup")

    container = Container()
    await container.init_resources()  # type: ignore

    container.wire(modules=[__name__])

    # Initialize the revocation processor and start background tasks

    # revocation_processor = await container.revocation_processor()  # type: ignore
    # await revocation_processor.start_background_processing()

    yield

    logger.debug("Shutting down Revocation service...")
    # Stop background processing

    # if revocation_processor:
    # await revocation_processor.stop_background_processing()

    await container.shutdown_resources()  # type: ignore
    logger.info("Revocation Service shutdown")


def create_app() -> FastAPI:
    openapi_name = os.getenv("OPENAPI_NAME", "Revocation Service")

    application = FastAPI(
        title=openapi_name,
        description="""
        Welcome to the OpenAPI interface for the Revocation Service.
        """,
        version=PROJECT_VERSION,
        lifespan=app_lifespan,
        redoc_url=None,
        docs_url=None,
    )

    return application


logger.info("Revocation Service startup")

app = create_app()


# Use Scalar instead of Swagger
@app.get("/docs", include_in_schema=False)
async def scalar_html() -> HTMLResponse:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}

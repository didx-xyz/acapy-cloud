import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from shared.constants import BUCKET_NAME, PROJECT_VERSION
from shared.log_config import get_logger
from tails.routers.tails import get_s3_client
from tails.routers.tails import router as tails_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    openapi_name = os.getenv("OPENAPI_NAME", "Tails Service")

    application = FastAPI(
        title=openapi_name,
        description="""
        Welcome to the OpenAPI interface for the Tails Service.
        The Tails Service forwards tails files to S3.
        """,
        version=PROJECT_VERSION,
        redoc_url=None,
        docs_url=None,
    )

    application.include_router(tails_router)
    return application


logger.info("Tails Service startup")

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
    """Health check endpoint"""
    try:
        s3_client = get_s3_client()
        # Test S3 connection
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        return {"status": "healthy", "s3_connection": "ok"}
    except Exception:
        logger.exception("Health check failed")
        return {"status": "unhealthy", "error": "s3 connection failed"}

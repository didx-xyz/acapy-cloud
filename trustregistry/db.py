from collections.abc import AsyncGenerator, Generator

from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Session, mapped_column

from trustregistry.database import AsyncSessionLocal, Base, SessionLocal
from trustregistry.list_type import StringList


def get_db() -> Generator[Session, None, None]:
    """Sync database session dependency for migration and sync operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency for application use."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def schema_id_gen(context) -> str:  # noqa: ANN001
    parameters = context.get_current_parameters()
    did = parameters["did"]
    name = parameters["name"]
    version = parameters["version"]
    return f"{did}:2:{name}:{version}"


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    roles: Mapped[str] = mapped_column(StringList, index=True)
    didcomm_invitation: Mapped[str | None] = mapped_column(
        String, unique=True, index=True
    )
    did: Mapped[str] = mapped_column(String, unique=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String, index=True)


class Schema(Base):
    __tablename__ = "schemas"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        index=True,
        unique=True,
        default=schema_id_gen,
        onupdate=schema_id_gen,
    )
    did: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[str] = mapped_column(String, index=True)

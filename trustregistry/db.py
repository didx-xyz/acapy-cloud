from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from trustregistry.database import Base, SessionLocal
from trustregistry.list_type import StringList


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def schema_id_gen(context):
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
    didcomm_invitation: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True
    )
    did: Mapped[str] = mapped_column(String, unique=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String, index=True)


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

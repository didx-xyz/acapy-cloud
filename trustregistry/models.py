from sqlalchemy import Column, String

from .database import Base


class Actor(Base):
    __tablename__ = "actors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    roles = Column(String, index=True)
    didcomm_invitation = Column(String, unique=True, index=True)
    did = Column(String, unique=True, index=True)


class Schema(Base):
    __tablename__ = "schemas"

    did = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    version = Column(String, index=True)

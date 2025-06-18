from enum import Enum
from typing import NamedTuple, Optional

from shared.constants import (
    GOVERNANCE_AGENT_API_KEY,
    GOVERNANCE_AGENT_URL,
    TENANT_AGENT_API_KEY,
    TENANT_AGENT_URL,
)


class AgentType(NamedTuple):
    name: str
    base_url: str
    is_multitenant: bool
    is_admin: bool
    x_api_key: str


GOVERNANCE_AGENT_TYPE = AgentType(
    name="governance",
    base_url=GOVERNANCE_AGENT_URL,
    is_multitenant=False,
    is_admin=True,
    x_api_key=GOVERNANCE_AGENT_API_KEY,
)

TENANT_ADMIN_AGENT_TYPE = AgentType(
    name="tenant-admin",
    base_url=TENANT_AGENT_URL,
    is_multitenant=True,
    is_admin=True,
    x_api_key=TENANT_AGENT_API_KEY,
)

TENANT_AGENT_TYPE = AgentType(
    name="tenant",
    base_url=TENANT_AGENT_URL,
    is_multitenant=True,
    is_admin=False,
    x_api_key=TENANT_AGENT_API_KEY,
)


class Role(Enum):
    GOVERNANCE = GOVERNANCE_AGENT_TYPE
    TENANT_ADMIN = TENANT_ADMIN_AGENT_TYPE
    TENANT = TENANT_AGENT_TYPE

    @staticmethod
    def from_str(role: str) -> Optional["Role"]:
        for item in Role:
            if item.role_name == role:
                return item

        return None

    @property
    def role_name(self) -> str:
        return self.value.name

    @property
    def agent_type(self) -> AgentType:
        return self.value

    @property
    def is_admin(self) -> bool:
        return self.value.is_admin

    @property
    def is_multitenant(self) -> bool:
        return self.value.is_multitenant

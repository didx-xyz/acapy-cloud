from enum import Enum
from typing import NamedTuple, Optional

from app.constants import (
    ECOSYSTEM_AGENT_API_KEY,
    ECOSYSTEM_AGENT_URL,
    MEMBER_AGENT_API_KEY,
    MEMBER_AGENT_URL,
    GOVERNANCE_AGENT_API_KEY,
    GOVERNANCE_AGENT_URL,
)


class AgentType(NamedTuple):
    name: str
    base_url: str
    is_multitenant: bool
    tenant_role: Optional["AgentType"]
    is_admin: bool
    x_api_key: Optional[str]


GOVERNANCE_AGENT_TYPE = AgentType(
    name="governance",
    base_url=GOVERNANCE_AGENT_URL,
    is_multitenant=False,
    tenant_role=None,
    is_admin=True,
    x_api_key=GOVERNANCE_AGENT_API_KEY,
)

ECOSYSTEM_AGENT_TYPE = AgentType(
    name="ecosystem",
    base_url=ECOSYSTEM_AGENT_URL,
    is_multitenant=True,
    tenant_role=None,
    is_admin=False,
    x_api_key=ECOSYSTEM_AGENT_API_KEY,
)

ECOSYSTEM_ADMIN_AGENT_TYPE = AgentType(
    name="ecosystem-admin",
    base_url=ECOSYSTEM_AGENT_URL,
    is_multitenant=True,
    tenant_role=ECOSYSTEM_AGENT_TYPE,
    is_admin=True,
    x_api_key=ECOSYSTEM_AGENT_API_KEY,
)

MEMBER_AGENT_TYPE = AgentType(
    name="member",
    base_url=MEMBER_AGENT_URL,
    is_multitenant=True,
    tenant_role=None,
    is_admin=False,
    x_api_key=MEMBER_AGENT_API_KEY,
)

MEMBER_ADMIN_AGENT_TYPE = AgentType(
    name="member-admin",
    base_url=MEMBER_AGENT_URL,
    is_multitenant=True,
    tenant_role=MEMBER_AGENT_TYPE,
    is_admin=True,
    x_api_key=MEMBER_AGENT_API_KEY,
)


class Role(Enum):
    GOVERNANCE = GOVERNANCE_AGENT_TYPE
    ECOSYSTEM = ECOSYSTEM_AGENT_TYPE
    ECOSYSTEM_ADMIN = ECOSYSTEM_ADMIN_AGENT_TYPE
    MEMBER = MEMBER_AGENT_TYPE
    MEMBER_ADMIN = MEMBER_ADMIN_AGENT_TYPE

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

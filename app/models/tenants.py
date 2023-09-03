from typing import List, Optional

from aries_cloudcontroller import CreateWalletRequest
from aries_cloudcontroller.model.wallet_record import WalletRecord
from pydantic import BaseModel, Field, HttpUrl
from pydantic.networks import AnyHttpUrl

from app.services.trust_registry import TrustRegistryRole


class CreateWalletRequestWithGroups(CreateWalletRequest):
    group_id: Optional[str] = None


class WalletRecordWithGroups(WalletRecord):
    group_id: Optional[str] = Field(None, example="SomeGroupId")


class WalletListWithGroups(BaseModel):
    results: Optional[List[WalletRecordWithGroups]] = None


class TenantRequestBase(BaseModel):
    image_url: Optional[HttpUrl] = Field(
        None, example="https://yoma.africa/images/sample.png"
    )


class CreateTenantRequest(TenantRequestBase):
    name: str = Field(..., example="Yoma")  # used as label and trust registry name
    roles: Optional[List[TrustRegistryRole]] = None
    group_id: Optional[str] = Field(None, example="SomeGroupId")


class UpdateTenantRequest(TenantRequestBase):
    name: Optional[str] = Field(
        None, example="Yoma"
    )  # used as label and trust registry name
    roles: Optional[List[TrustRegistryRole]] = None
    group_id: Optional[str] = Field(None, example="SomeGroupId")


class Tenant(BaseModel):
    tenant_id: str = Field(..., example="545135a4-ecbc-4400-8594-bdb74c51c88d")
    tenant_name: str = Field(..., example="Alice")
    image_url: Optional[str] = Field(None, example="https://yoma.africa/image.png")
    created_at: str = Field(...)
    updated_at: Optional[str] = Field(None)
    group_id: Optional[str] = Field(None, example="SomeGroupId")


class TenantAuth(BaseModel):
    access_token: str = Field(..., example="ey...")


class CreateTenantResponse(Tenant, TenantAuth):
    pass


class OnboardResult(BaseModel):
    did: str
    didcomm_invitation: Optional[AnyHttpUrl] = None

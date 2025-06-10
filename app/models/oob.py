from aries_cloudcontroller import AttachmentDef, InvitationMessage
from pydantic import BaseModel, model_validator

from shared.exceptions.cloudapi_value_error import CloudApiValueError


class ConnectToPublicDid(BaseModel):
    public_did: str


class CreateOobInvitation(BaseModel):
    alias: str | None = None
    multi_use: bool | None = None
    use_public_did: bool | None = None
    attachments: list[AttachmentDef] | None = None
    create_connection: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_one_of_create_connection_or_attachments(cls, values):
        create, attachments = values.get("create_connection"), values.get("attachments")
        if not create and not attachments:
            raise CloudApiValueError(
                "One or both of 'create_connection' and 'attachments' must be included."
            )
        return values


class AcceptOobInvitation(BaseModel):
    alias: str | None = None
    use_existing_connection: bool | None = None
    invitation: InvitationMessage

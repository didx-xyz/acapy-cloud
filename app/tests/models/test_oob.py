import pytest

from app.models.oob import CreateOobInvitation
from shared.exceptions.cloudapi_value_error import CloudApiValueError


def test_create_oob_invitation_model() -> None:
    CreateOobInvitation(create_connection=True)

    with pytest.raises(CloudApiValueError) as exc:
        CreateOobInvitation(create_connection=None, attachments=None)
    assert exc.value.detail == (
        "One or both of 'create_connection' and 'attachments' must be included."
    )

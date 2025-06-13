import re
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, field_validator

from app.exceptions.handle_model_with_validation import handle_model_with_validation
from shared.exceptions import CloudApiValueError

error_msg = "must validate the regular expression ..."


class DummyModel(BaseModel):
    field: str

    @field_validator("field")
    @classmethod
    def validate_regex(cls, value: str) -> str:
        """Validates the regular expression"""
        if not re.match(r"^[\d+]$", value):
            raise ValueError(error_msg)
        return value


@pytest.mark.anyio
async def test_handle_model_with_validation_error():
    mock_logger = Mock()
    # Replace the class itself with a mock that raises ValidationError on instantiation
    with pytest.raises(CloudApiValueError) as exc_info:
        handle_model_with_validation(mock_logger, DummyModel, field="invalid")

    enriched_error_msg = f"field {error_msg}"
    assert enriched_error_msg in str(exc_info.value)
    mock_logger.info.assert_called_with(
        "Bad request: Validation error from {} body: {}",
        "DummyModel",
        enriched_error_msg,
    )

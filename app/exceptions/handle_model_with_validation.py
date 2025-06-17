from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.util.extract_validation_error import extract_validation_error_msg
from shared.exceptions import CloudApiValueError
from shared.log_config import Logger

T = TypeVar("T", bound=BaseModel)


def handle_model_with_validation(logger: Logger, model_class: type[T], **kwargs) -> T:
    """Attempts to create an instance of a Pydantic model with the given arguments.
    Logs and raises an CloudApiException if a ValidationError occurs.

    Args:
        logger: Logger instance for logging the error.
        model_class: The Pydantic model class to instantiate.
        **kwargs: Keyword arguments to be passed to the model class for instantiation.

    Returns:
        An instance of the model class if validation succeeds.

    Raises:
        CloudApiException with status_code=422 if validation fails.

    """
    try:
        model_instance = model_class(**kwargs)
        return model_instance
    except ValidationError as e:
        error_msg = extract_validation_error_msg(e)
        model_name = model_class.__name__
        logger.info(
            "Bad request: Validation error from {} body: {}", model_name, error_msg
        )
        raise CloudApiValueError(detail=error_msg) from e

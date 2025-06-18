from typing import TypeVar

from pydantic import BaseModel, ValidationError

from shared.log_config import Logger

# Define generic type for `parse_json_with_error_handling`
T = TypeVar("T", bound=BaseModel)


def parse_json_with_error_handling(model: type[T], data: str, logger: Logger) -> T:
    try:
        return model.model_validate_json(data)
    except ValidationError as e:
        logger.error(
            "Could not parse data into {} object. Error: `{}`.", model.__name__, e
        )
        raise

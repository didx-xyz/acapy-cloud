from pydantic import BaseModel, ValidationError

from shared.log_config import Logger


def parse_json_with_error_handling[T: BaseModel](
    model: type[T], data: str, logger: Logger
) -> T:
    """Parse generic model type T from JSON string with error handling."""
    try:
        return model.model_validate_json(data)
    except ValidationError as e:
        logger.error(
            "Could not parse data into {} object. Error: `{}`.", model.__name__, e
        )
        raise

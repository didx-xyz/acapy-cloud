from fastapi import Query
from pydantic import BaseModel, Field

save_exchange_record_description = (
    "Controls exchange record retention after exchange is complete. None uses "
    "wallet default (typically to delete), true forces save, false forces delete."
)

save_exchange_record_field = Field(
    default=None,
    description=save_exchange_record_description,
)

save_exchange_record_query = Query(
    default=None,
    description=save_exchange_record_description,
)


class SaveExchangeRecordField(BaseModel):
    save_exchange_record: bool | None = save_exchange_record_field

    @property
    def auto_remove(self) -> bool | None:
        """Returns the inverse of save_exchange_record if set, otherwise None."""
        if isinstance(self.save_exchange_record, bool):
            return not self.save_exchange_record
        return None

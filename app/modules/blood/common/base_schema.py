# app/modules/blood/common/base_schema.py

from pydantic import BaseModel, ConfigDict

def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        str_strip_whitespace=True,
        extra="forbid",  # 🔥 strict mode for audit
        validate_assignment=True,
    )
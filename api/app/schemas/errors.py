"""The error envelope as contract models — only for the OpenAPI document (06 §C)."""

from typing import Any

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from app.schemas import ApiModel


class ApiErrorBody(ApiModel):
    code: str = Field(
        description="`validation` · `unauthorized` · `forbidden` · `not_found` · `conflict` · "
        "`rate_limited` · `unavailable` · `internal`, plus business codes such as "
        "`seat_taken`, `hold_missing`, `too_many_seats`, `has_sales`."
    )
    message: str
    # Optional but never null on the wire (the handlers omit the key), hence SkipJsonSchema.
    details: dict[str, Any] | SkipJsonSchema[None] = Field(
        default=None,
        description="Code-specific payload, e.g. `{taken: seat_id[]}` or `{fields: {path: msg}}`.",
    )


class ApiErrorResponse(ApiModel):
    error: ApiErrorBody

"""pydantic v2 request/response models — the API contract (05 §2).

Field names are snake_case on the wire, exactly as docs/06-data-and-api.md §D writes them
(`seat_id`, `expires_at`, `server_time`); the generated TypeScript mirrors that.
"""

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

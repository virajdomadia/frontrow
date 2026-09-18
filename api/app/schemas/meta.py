from app.schemas import ApiModel


class Health(ApiModel):
    ok: bool
    service: str
    version: str

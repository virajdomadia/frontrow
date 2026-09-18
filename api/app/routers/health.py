from fastapi import APIRouter

from app.schemas.meta import Health

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(ok=True, service="frontrow-api", version="0.1.0")

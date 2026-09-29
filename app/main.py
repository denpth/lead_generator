from fastapi import FastAPI

from app.api.routes.leads import router as leads_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.reviews import router as reviews_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)
app.include_router(leads_router)
app.include_router(decisions_router)
app.include_router(reviews_router)


@app.get("/healthz", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

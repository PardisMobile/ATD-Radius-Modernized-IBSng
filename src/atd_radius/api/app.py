from fastapi import FastAPI

from atd_radius import __version__
from atd_radius.config import settings
from atd_radius.api.users import router as users_router

app = FastAPI(title=settings.app_name, version=__version__)
app.include_router(users_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get(f"{settings.api_prefix}/meta")
def meta() -> dict[str, str]:
    return {"name": settings.app_name, "version": __version__, "reference": "IBSng A1.24"}

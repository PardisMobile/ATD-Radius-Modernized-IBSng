import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from atd_radius import __version__
from atd_radius.config import settings
from atd_radius.api.admin_auth import router as admin_auth_router
from atd_radius.api.admin_deposits import router as admin_deposits_router
from atd_radius.api.admins import router as admins_router
from atd_radius.api.groups import router as groups_router
from atd_radius.api.ras import router as ras_router
from atd_radius.api.users import router as users_router
from atd_radius.api.voip_tariffs import router as voip_tariffs_router
from atd_radius.api.voip_charge_rules import router as voip_charge_rules_router
from atd_radius.api.internet_charge_rules import router as internet_charge_rules_router
from atd_radius.api.bandwidth_manager import router as bandwidth_manager_router
from atd_radius.api.charges import router as charges_router
from atd_radius.api.ias_events import router as ias_events_router
from atd_radius.api.ias_users import router as ias_users_router

app = FastAPI(title=settings.app_name, version=__version__)


@app.middleware("http")
async def enforce_api_bearer_token(request: Request, call_next):
    """Protect API routes when configured; fail closed outside development/test."""
    path = request.url.path
    if path != settings.api_prefix and not path.startswith(settings.api_prefix + "/"):
        return await call_next(request)

    token = settings.api_bearer_token.strip()
    if not token and settings.environment.casefold() not in {"development", "test"}:
        return JSONResponse(
            status_code=503,
            content={"detail": "API authentication is not configured"},
        )

    if token:
        scheme, separator, supplied = request.headers.get("authorization", "").partition(" ")
        if (
            scheme.casefold() != "bearer"
            or not separator
            or not hmac.compare_digest(supplied, token)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    return await call_next(request)
app.include_router(admin_auth_router, prefix=settings.api_prefix)
app.include_router(admin_deposits_router, prefix=settings.api_prefix)
app.include_router(admins_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(groups_router, prefix=settings.api_prefix)
app.include_router(ras_router, prefix=settings.api_prefix)
app.include_router(voip_tariffs_router, prefix=settings.api_prefix)
app.include_router(voip_charge_rules_router, prefix=settings.api_prefix)
app.include_router(internet_charge_rules_router, prefix=settings.api_prefix)
app.include_router(bandwidth_manager_router, prefix=settings.api_prefix)
app.include_router(charges_router, prefix=settings.api_prefix)
app.include_router(ias_events_router, prefix=settings.api_prefix)
app.include_router(ias_users_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get(f"{settings.api_prefix}/meta")
def meta() -> dict[str, str]:
    return {"name": settings.app_name, "version": __version__, "reference": "IBSng A1.24"}

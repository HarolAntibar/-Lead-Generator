from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.features.auth import models as _auth_models  # noqa: F401 — registers User in SQLAlchemy metadata
from app.features.businesses.router import router as businesses_router
from app.features.campaigns.router import router as campaigns_router
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify database connection
    async with engine.connect():
        pass
    yield
    # Shutdown: close all database connections
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Lead Generator",
        # Disable API docs in production (no public exposure)
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.is_production,
    )

    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

    app.include_router(web_router)
    app.include_router(campaigns_router)
    app.include_router(businesses_router)

    register_exception_handlers(app)

    return app


app = create_app()

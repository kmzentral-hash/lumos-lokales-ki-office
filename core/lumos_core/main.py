import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .config import settings
from .documents import router as documents_router
from .export import router as export_router
from .llm import LLMUnsafeBaseUrlError, provider_from_settings
from .search import router as search_router

logger = logging.getLogger("uvicorn.error")


def _registered_routes(application: FastAPI) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []

    def visit(route: object) -> None:
        children = getattr(route, "routes", None)
        if children is not None:
            for child in children:
                visit(child)
            return
        path = getattr(route, "path", None)
        if path is not None:
            methods = ",".join(sorted(getattr(route, "methods", set()) or set()))
            result.append((methods, path))

    for registered in application.routes:
        visit(registered)
    known = set(result)
    for path, operations in application.openapi()["paths"].items():
        methods = ",".join(sorted(method.upper() for method in operations))
        route = (methods, path)
        if route not in known:
            result.append(route)
    return sorted(result, key=lambda item: item[1])


@asynccontextmanager
async def lifespan(application: FastAPI):
    logger.info("Registrierte LumOS-Routen:")
    for methods, path in _registered_routes(application):
        logger.info("  %-12s %s", methods, path)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:1420", "http://localhost:1420"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(export_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/docs", include_in_schema=False)
async def legacy_docs() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
async def health() -> dict[str, object]:
    llm_configured = False
    llm_reachable = False
    llm_base_url = settings.llm_base_url
    try:
        llm_provider = provider_from_settings()
        status = await llm_provider.status()
        llm_configured = status.configured
        llm_reachable = status.reachable
        llm_base_url = status.base_url
        llm_state = "reachable" if llm_reachable else ("configured" if llm_configured else "not_configured")
    except LLMUnsafeBaseUrlError:
        llm_state = "invalid_base_url"

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "local_only": settings.host == "127.0.0.1",
        "components": {
            "database": "ready",
            "documents": "ready",
            "export": "ready",
            "llm": llm_state,
            "retrieval": "ready",
            "search": "ready",
        },
        "llm_details": {
            "configured": llm_configured,
            "reachable": llm_reachable,
            "base_url": llm_base_url,
        },
    }

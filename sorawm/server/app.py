from fastapi import FastAPI

from sorawm.server.lifespan import lifespan
from sorawm.server.router import router as backend_router
from sorawm.server.front_router import router as front_router


def init_app():
    """
    Create and configure the FastAPI application with the application lifespan and route groups.

    Includes the backend API router under the "/api/v1" prefix and the frontend router at the top level.

    Returns:
        FastAPI: Configured FastAPI application instance.
    """
    app = FastAPI(lifespan=lifespan)
    app.include_router(backend_router, prefix="/api/v1")
    app.include_router(front_router)
    return app

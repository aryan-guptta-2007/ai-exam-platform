from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, exams, processing, ws

api_router = APIRouter()

# Register endpoint sub-routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(exams.router, prefix="/exams", tags=["exams"])
api_router.include_router(processing.router, prefix="/processing", tags=["processing"])
# Note: WebSocket endpoints are handled separately in main or via router inclusion
api_router.include_router(ws.router, tags=["websockets"])

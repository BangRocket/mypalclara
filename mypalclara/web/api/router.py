"""Mount all API sub-routers."""

from fastapi import APIRouter

from mypalclara.web.api.admin import router as admin_router
from mypalclara.web.api.graph import router as graph_router
from mypalclara.web.api.intentions import router as intentions_router
from mypalclara.web.api.memories import router as memories_router
from mypalclara.web.api.sessions import router as sessions_router
from mypalclara.web.api.users import router as users_router

api_router = APIRouter()

api_router.include_router(memories_router, prefix="/memories", tags=["memories"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(intentions_router, prefix="/intentions", tags=["intentions"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])

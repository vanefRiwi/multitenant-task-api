from fastapi import APIRouter

from app.presentation.http.routes import auth, tasks, tenants

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(tenants.members_router)
api_router.include_router(tasks.router)

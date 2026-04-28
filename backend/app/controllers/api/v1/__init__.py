from fastapi import APIRouter

from app.controllers.api.v1.auth_controller import router as auth_router
from app.controllers.api.v1.shipments_controller import router as shipments_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(shipments_router)

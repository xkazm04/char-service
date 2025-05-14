from fastapi import APIRouter
from routes.asset import router as asset_router
from routes.character import router as character_router

api_router = APIRouter()

api_router.include_router(asset_router, prefix="/assets", tags=["Assets"])
api_router.include_router(character_router, prefix="/characters", tags=["Characters"])
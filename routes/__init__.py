from fastapi import APIRouter
from routes.asset import router as asset_router
from routes.character import router as character_router
from routes.leo import router as leo_router
from routes.meshy import router as meshy_router
from routes.generation import router as generation_router
from routes.search import router as search_router
from routes.asset_search import router as asset_search_router
from routes.analyze import router as analyze_router

api_router = APIRouter()

api_router.include_router(asset_router, prefix="/assets", tags=["Assets"])
api_router.include_router(character_router, prefix="/characters", tags=["Characters"])
api_router.include_router(leo_router, prefix="/leo", tags=["Leo"])
api_router.include_router(meshy_router, prefix="/meshy", tags=["Meshy"])
api_router.include_router(generation_router, prefix="/gen", tags=["Generations"])
api_router.include_router(search_router, prefix="/search", tags=["Search"])
api_router.include_router(asset_search_router, prefix="/asset-search", tags=["Asset Search"])
api_router.include_router(analyze_router, prefix="/analyze", tags=["Analyze"])

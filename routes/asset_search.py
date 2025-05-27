from fastapi import APIRouter, HTTPException, Query, Body
from typing import List
from models.asset import AssetCreate
from services.atlas_asset_search import (
    asset_vector_search_service, 
    AssetSearchQuery, 
    AssetSearchResult
)
from services.asset_save import validate_asset_hybrid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["asset-search"])

@router.post("/semantic", response_model=List[AssetSearchResult])
async def search_assets_semantic(search_query: AssetSearchQuery):
    """
    Perform semantic search on assets using natural language.
    
    Examples:
    - "blue armor pieces"
    - "fantasy sword weapons"
    - "elf hairstyles"
    - "red clothing items"
    """
    try:
        results = await asset_vector_search_service.atlas_vector_search(search_query)
        return results
    except Exception as e:
        logger.error(f"Asset semantic search failed: {e}")
        raise HTTPException(status_code=500, detail="Asset search operation failed")

@router.get("/semantic", response_model=List[AssetSearchResult])
async def search_assets_semantic_get(
    query: str = Query(..., description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    min_score: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score"),
    asset_type: str = Query(None, description="Filter by asset type")
):
    """
    GET endpoint for semantic asset search (for easy testing).
    """
    search_query = AssetSearchQuery(
        query=query,
        limit=limit,
        min_score=min_score,
        asset_type=asset_type
    )
    return await search_assets_semantic(search_query)

@router.post("/similar", response_model=List[AssetSearchResult])
async def find_similar_assets_enhanced(
    asset: AssetCreate = Body(...),
    threshold: float = Query(0.90, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Find assets similar to the provided one using Atlas Vector Search.
    Returns similarity_mongo scores for comparison.
    """
    try:
        results = await asset_vector_search_service.find_similar_assets_atlas(
            asset, threshold=threshold, limit=limit
        )
        return results
    except Exception as e:
        logger.error(f"Similar asset search failed: {e}")
        raise HTTPException(status_code=500, detail="Similar asset search operation failed")

@router.post("/validate-enhanced")
async def validate_asset_enhanced(
    asset: AssetCreate = Body(...),
    use_atlas_search: bool = Query(True, description="Use Atlas Vector Search (true) or manual similarity (false)"),
    threshold: float = Query(0.95, ge=0.0, le=1.0, description="Similarity threshold")
):
    """
    Enhanced asset validation using Atlas Vector Search.
    Includes similarity_mongo scores and search method information.
    """
    try:
        result = await validate_asset_hybrid(
            asset, 
            use_atlas_search=use_atlas_search,
            threshold=threshold
        )
        
        # Remove description_vector before returning to frontend
        if "description_vector" in result:
            del result["description_vector"]
            
        return result
    except Exception as e:
        logger.error(f"Enhanced asset validation failed: {e}")
        raise HTTPException(status_code=500, detail="Asset validation operation failed")

@router.post("/reindex")
async def reindex_assets():
    """
    Reindex all assets without embeddings.
    """
    try:
        count = await asset_vector_search_service.reindex_all_assets()
        return {"message": f"Successfully reindexed {count} assets"}
    except Exception as e:
        logger.error(f"Asset reindexing failed: {e}")
        raise HTTPException(status_code=500, detail="Asset reindexing operation failed")

@router.get("/index-definition")
async def get_asset_index_definition():
    """
    Get the vector search index definition for Atlas setup.
    """
    try:
        index_def = await asset_vector_search_service.create_vector_search_index()
        return {
            "message": "Use this definition to create the vector search index in Atlas",
            "index_definition": index_def,
            "instructions": [
                "1. Go to Atlas UI > Search > Create Index",
                "2. Choose 'JSON Editor'", 
                "3. Use the index_definition provided below",
                "4. Name the index 'asset_vector_index'",
                "5. Ensure your collection has description_vector field populated"
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get asset index definition: {e}")
        raise HTTPException(status_code=500, detail="Failed to get index definition")
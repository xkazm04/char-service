from fastapi import APIRouter, HTTPException, Query
from typing import List
from models.generation import GenerationSearchQuery, GenerationSearchResult
from services.atlas_gen_search import atlas_search_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

@router.post("/generations", response_model=List[GenerationSearchResult])
async def search_generations(search_query: GenerationSearchQuery):
    """
    Perform semantic search on generations using natural language.
    
    Examples:
    - "fantasy warrior with blue armor"
    - "cute anime character with pink hair"
    - "dark mysterious mage"
    - "cyberpunk robot"
    """
    try:
        results = await atlas_search_service.semantic_search(search_query)
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search operation failed")

@router.get("/generations", response_model=List[GenerationSearchResult])
async def search_generations_get(
    query: str = Query(..., description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    min_score: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score")
):
    """
    GET endpoint for semantic search (for easy testing).
    """
    search_query = GenerationSearchQuery(
        query=query,
        limit=limit,
        min_score=min_score
    )
    return await search_generations(search_query)

@router.post("/reindex")
async def reindex_generations():
    """
    Reindex all generations without embeddings.
    """
    try:
        count = await atlas_search_service.reindex_all_generations()
        return {"message": f"Successfully reindexed {count} generations"}
    except Exception as e:
        logger.error(f"Reindexing failed: {e}")
        raise HTTPException(status_code=500, detail="Reindexing operation failed")

@router.get("/index-definition")
async def get_index_definition():
    """
    Get the vector search index definition for Atlas setup.
    """
    try:
        index_def = await atlas_search_service.create_vector_search_index()
        return {
            "message": "Use this definition to create the vector search index in Atlas",
            "index_definition": index_def,
            "instructions": [
                "1. Go to Atlas UI > Search > Create Index",
                "2. Choose 'JSON Editor'",
                "3. Use the index_definition provided below",
                "4. Name the index 'vector_index'"
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get index definition: {e}")
        raise HTTPException(status_code=500, detail="Failed to get index definition")

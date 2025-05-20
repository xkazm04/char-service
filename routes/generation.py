from fastapi import APIRouter, Query, HTTPException, Path
from typing import List, Optional
from bson import ObjectId
from models.generation import GenerationResponse
from database import generation_collection

router = APIRouter()

@router.get("/", response_model=List[GenerationResponse])
async def get_generations(
    character_id: Optional[str] = Query(None, description="Filter by character ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max number of records to return")
):
    """
    Get image generations from the database with optional character_id filtering
    and pagination. Returns 20 generations by default.
    """
    filter_query = {}
    
    if character_id:
        if not ObjectId.is_valid(character_id):
            raise HTTPException(status_code=400, detail="Invalid character_id format")
        filter_query["character_id"] = ObjectId(character_id)
    
    projection = {"description_vector": 0}
    
    generations = await generation_collection.find(
        filter_query, 
        projection
    ).skip(skip).limit(limit).to_list(limit)
    
    return generations

@router.delete("/{generation_id}", status_code=204)
async def delete_generation(
    generation_id: str = Path(..., description="The ID of the generation to delete")
):
    """
    Delete a generation by its ID
    """
    if not ObjectId.is_valid(generation_id):
        raise HTTPException(status_code=400, detail="Invalid generation_id format")
    
    result = await generation_collection.delete_one({"_id": ObjectId(generation_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    return None
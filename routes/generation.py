from fastapi import APIRouter, Query, HTTPException, Path
from typing import List, Optional
from bson import ObjectId
from models.generation import GenerationResponse
from database import generation_collection
from services.leo import delete_generation_api
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[GenerationResponse])
async def get_generations(
    character_id: Optional[str] = Query(
        None, description="Filter by character ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        20, ge=1, le=100, description="Max number of records to return")
):
    """
    Get image generations from the database with optional character_id filtering
    and pagination. Returns 20 generations by default.
    """
    filter_query = {}

    if character_id:
        if not ObjectId.is_valid(character_id):
            raise HTTPException(
                status_code=400, detail="Invalid character_id format")
        
        # Convert to ObjectId for the query
        character_obj_id = ObjectId(character_id)
        
        # Query for both ObjectId and string formats to handle data inconsistency
        filter_query["character_id"] = {
            "$in": [character_obj_id, character_id]
        }
        
        # Debug: Log the query being executed
        logger.info(f"Querying with character_id: {character_id} (ObjectId: {character_obj_id})")
        
        # Debug: Check what's actually in the database
        sample_docs = await generation_collection.find({}).limit(5).to_list(5)
        logger.info(f"Sample documents in collection:")
        for doc in sample_docs:
            logger.info(f"  - character_id: {doc.get('character_id')} (type: {type(doc.get('character_id'))})")

    projection = {"description_vector": 0}

    # Debug: Log the final filter query
    logger.info(f"Final filter query: {filter_query}")

    generations = await generation_collection.find(
        filter_query,
        projection
    ).skip(skip).limit(limit).to_list(limit)
    
    # Debug: Log the results
    logger.info(f"Found {len(generations)} generations matching the query")

    return generations


@router.delete("/{generation_id}", status_code=204)
async def delete_generation(
    generation_id: str = Path(...,
    description="The ID of the generation to delete")
):
    """
    Delete a generation by its ID
    """
    if not ObjectId.is_valid(generation_id):
        raise HTTPException(
            status_code=400, detail="Invalid generation_id format")

    item = await generation_collection.find_one(
        {"_id": ObjectId(generation_id)}
    )
    if not item:
        logger.warning(
            f"Generation with ID {generation_id} not found in collection")
    result = await generation_collection.delete_one({"_id": ObjectId(generation_id)})

    try:
        if item: 
            delete_generation_api(item.get("leo_id", generation_id))
            logger.info(f"Deleted generation with ID: {generation_id}")
        else:
            logger.warning(f"Generation with ID {generation_id} not found in collection")
    except Exception as e:
        logger.error(f"Error in delete_generations: {e}", exc_info=True)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Generation not found")

    return None



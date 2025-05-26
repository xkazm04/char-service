import logging 
from typing import List, Dict, Any, Optional
from services.image_save import download_image, get_embedding, serialize_for_json
from models.generation import GenerationBase, UsedAssets
from bson import ObjectId
from database import generation_collection
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_all_generations() -> List[Dict[str, Any]]:
    """
    Retrieve all generations from the database.
    """
    try:
        logger.info("Fetching all generations from the database.")
        generations = list(generation_collection.find({}))
        logger.info(f"Retrieved {len(generations)} generations.")
        # Remove description_embedding from the serialized output
        for gen in generations:
            if "description_vector" in gen:
                del gen["description_vector"]
        return [serialize_for_json(gen) for gen in generations]
    except Exception as e:
        logger.error(f"Error fetching generations: {e}", exc_info=True)
        return []


async def save_generation(
    leo_id: str,
    character_id: str,
    image_url: Optional[str] = None,
    description: Optional[str] = None,
    used_assets: Optional[List[UsedAssets]] = None,
) -> Dict[str, Any]:
    """
    Save generation data to the database, including image data if URL is provided.
    """
    try:
        logger.info(f"Starting save_generation for character: {character_id}")
        logger.info(f"Used assets provided: {len(used_assets) if used_assets else 0}")
        
        # Convert character_id to ObjectId if it's a string
        if isinstance(character_id, str):
            if not ObjectId.is_valid(character_id):
                logger.error(f"Invalid ObjectId format: {character_id}")
                return {
                    "status": "error",
                    "message": f"Invalid character_id format: {character_id}"
                }
            char_id = ObjectId(character_id)
        else:
            char_id = character_id

        description_embedding = await get_embedding(description)
        logger.info(f"Created description embedding of length: {len(description_embedding)}")
        
        # Process image if URL is provided
        image_data = None
        content_type = None
        if image_url:
            logger.info(f"Downloading image from URL: {image_url}")
            image_data, content_type = await download_image(image_url)
            logger.info(f"Downloaded image of type: {content_type}, size: {len(image_data) / 1024:.2f} KB")
    
        # Process used assets if provided
        processed_used_assets = None
        if used_assets:
            processed_used_assets = []
            for asset in used_assets:
                # Convert UsedAssets model to dict for MongoDB
                asset_dict = asset.model_dump() if hasattr(asset, 'model_dump') else asset.dict()
                processed_used_assets.append(asset_dict)
            logger.info(f"Processed {len(processed_used_assets)} used assets for storage")
        
        # Create generation instance with current timestamp
        generation = GenerationBase(
            leo_id=leo_id,
            character_id=char_id,
            image_url=image_url,
            description=description,
            description_vector=description_embedding,
            used_assets=processed_used_assets,
            created_at=datetime.now()  # Explicitly set created_at
        )
        
        # Convert to dict for MongoDB insertion, but manually handle character_id as ObjectId
        generation_to_insert = generation.model_dump(by_alias=True, exclude={'character_id'})
        # Manually add character_id as ObjectId to preserve the type in MongoDB
        generation_to_insert['character_id'] = char_id
        
        logger.info(f"Prepared generation for insertion with fields: {list(generation_to_insert.keys())}")
        logger.info(f"character_id type in document: {type(generation_to_insert['character_id'])}")
        
        # Insert into database
        result = await generation_collection.insert_one(generation_to_insert)
        logger.info(f"Generation inserted with ID: {result.inserted_id}")
        
        created_generation = await generation_collection.find_one({"_id": result.inserted_id})
        
        if not created_generation:
            logger.warning(f"Could not retrieve newly created generation with ID: {result.inserted_id}")
            return {
                "id": str(result.inserted_id),
                "status": "saved",
                "message": "Generation saved but not retrieved"
            }
            
        serialized_generation = serialize_for_json(dict(created_generation))
        
        if "_id" in serialized_generation and "id" not in serialized_generation:
            serialized_generation["id"] = serialized_generation["_id"]
        
        logger.info(f"Generation saved successfully with ID: {serialized_generation.get('id')}")

        return {
            **serialized_generation,
            "status": "saved",
            "message": "Generation saved successfully"
        }
    
    except Exception as e:
        logger.error(f"Error in save_generation: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error saving generation: {str(e)}"
        }
import logging
from fastapi import APIRouter, HTTPException
from services.leo import get_generation, delete_generation_api, create_asset_img
from services.generation import save_generation
from services.image_save import save_asset_with_image, download_image
from models.asset import AssetCreate
import asyncio
from pydantic import BaseModel, Field
from typing import Optional

# Fix the logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Leo"])

class DeleteGenerationsRequest(BaseModel):
    generation_ids: list[str]

@router.post("/delete")
async def delete_generations(request: DeleteGenerationsRequest):
    try:  
        for generation_id in request.generation_ids:
            delete_generation_api(generation_id)
            logger.info(f"Deleted generation with ID: {generation_id}")
        return {"status": "success", "message": "Generations deleted successfully."}
    except Exception as e:
        logger.error(f"Error in delete_generations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class AssetImageGenerationRequest(BaseModel):
    gen: str  
    generation_id: Optional[str] = Field(None, description="Optional generation ID for retries")
    asset: AssetCreate = Field(..., description="Asset data to save")

@router.post("/asset")
async def generate_and_save_asset_image(request: AssetImageGenerationRequest):
    try:
        logger.info(f"Received asset-save request with gen: {request.gen}")
        
        # Validate that the asset object is present
        if not request.asset:
            raise HTTPException(status_code=400, detail="Missing asset object in request")
            
        # Validate required asset fields
        if not request.asset.type or not request.asset.name or not request.asset.gen:
            raise HTTPException(
                status_code=400, 
                detail="Asset missing required fields (type, name, or gen)"
            )
        
        # Handle previous generation if needed
        if request.generation_id:
            try:
                logger.info(f"Deleting previous generation with ID: {request.generation_id}")
                delete_generation_api(request.generation_id)
            except Exception as e:
                logger.warning(f"Failed to delete previous generation {request.generation_id}: {e}")

        # Generate image
        create_response = create_asset_img(gen=request.gen)
        
        generation_id = create_response["sdGenerationJob"]["generationId"]
        logger.info(f"Created new generation with ID: {generation_id}")
        images = None
        for attempt in range(12):  # 12 attempts x 5s = 60s max
            try:
                images = get_generation(generation_id)
                if images:  
                    logger.info(f"Images found after {attempt + 1} attempts.")
                    break
            except Exception as e:
                logger.warning(f"Polling attempt {attempt + 1} failed: {e}")

            await asyncio.sleep(5)  # Wait 5 seconds between polling attempts
        
        if not images:
            raise HTTPException(status_code=408, detail="Image generation timed out.")
        
        image_url = images[0]["url"]
        asset = request.asset
        if not asset.gen:
            asset.gen = request.gen
        
        try:
            image_data, content_type = await download_image(image_url)
            asset.image_data = image_data
            logger.info(f"Downloaded image data from {image_url}: {len(image_data)} bytes")
        except Exception as e:
            logger.warning(f"Failed to download image data from URL: {e}")
            # Continue with saving even if image download fails
        
        # Now save the asset with image data
        saved_result = await save_asset_with_image(asset, image_url)
        
        if saved_result.get("status") == "error":
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save asset: {saved_result.get('message')}"
            )
        
        if "description_vector" in saved_result:
            del saved_result["description_vector"]
        # Cleanup   
        try:  
            delete_generation_api(generation_id)
            logger.info(f"Deleted generation with ID: {generation_id}")
        except Exception as e:
            logger.error(f"Error in delete_generations: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
            
        return {
            "status": "success", 
            "asset": saved_result,
            "generation_id": generation_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_and_save_asset_image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class GenerationRequest(BaseModel):
    gen: str 
    element: int = Field(None, description="Element akUUID, e.g., 67297 for Jinx")
    generation_id: Optional[str] = Field(None, description="Optional generation ID for retries")
    description: Optional[str] = Field(None, description="Description for the generation")
    character_id: Optional[str] = Field(None, description="Character ID to associate with the generation")
    

@router.post("/generation")
async def generate_and_save_gen_image(request: GenerationRequest):
    try:
        logger.info(f"Received gen-save request with gen: {request.gen}")
        
        # Handle previous generation if needed
        if request.generation_id:
            try:
                logger.info(f"Deleting previous generation with ID: {request.generation_id}")
                delete_generation_api(request.generation_id)
            except Exception as e:
                logger.warning(f"Failed to delete previous generation {request.generation_id}: {e}")

        # Generate image
        create_response = create_asset_img(gen=request.gen)
        
        generation_id = create_response["sdGenerationJob"]["generationId"]
        logger.info(f"Created new generation with ID: {generation_id}")
        images = None
        for attempt in range(12):  # 12 attempts x 5s = 60s max
            try:
                images = get_generation(generation_id)
                if images:  
                    logger.info(f"Images found after {attempt + 1} attempts.")
                    break
            except Exception as e:
                logger.warning(f"Polling attempt {attempt + 1} failed: {e}")

            await asyncio.sleep(5)  # Wait 5 seconds between polling attempts
        
        if not images:
            raise HTTPException(status_code=408, detail="Image generation timed out.")
        
        image_url = images[0]["url"] 
        try:
            image_data = await download_image(image_url)
            logger.info(f"Downloaded image data from {image_url}: {len(image_data)} bytes")
        except Exception as e:
            logger.warning(f"Failed to download image data from URL: {e}")

        saved_result = await save_generation(
            character_id=request.character_id if request.character_id else "682cfdfaebbb3e6ada96d357", 
            image_url=image_url,
            description=request.description,
            leo_id=generation_id,
        )
        
        if saved_result.get("status") == "error":
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save asset: {saved_result.get('message')}"
            )
        
        if "description_vector" in saved_result:
            del saved_result["description_vector"]
        # Cleanup   
        # try:  
        #     delete_generation_api(generation_id)
        #     logger.info(f"Deleted generation with ID: {generation_id}")
        # except Exception as e:
        #     logger.error(f"Error in delete_generations: {e}", exc_info=True)
        #     raise HTTPException(status_code=500, detail=str(e))
            
        return {
            "status": "success", 
            "asset": saved_result,
            "generation_id": generation_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_and_save_asset_image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

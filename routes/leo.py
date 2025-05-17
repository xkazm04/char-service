import logging
from fastapi import APIRouter, HTTPException
from services.leo import get_generation, delete_generation_api, create_asset_img
from services.image_save import save_asset_with_image
from models.asset import AssetCreate
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


router = APIRouter(tags=["Leo"])

import logging
logger = logging.basicConfig(level=logging.INFO)
class DeleteGenerationsRequest(BaseModel):
    generation_ids: list[str]

@router.post("/delete")
async def delete_generations(request: DeleteGenerationsRequest):
    try:  
        for generation_id in request.generation_ids:
            delete_generation_api(generation_id)
            logging.info(f"Deleted generation with ID: {generation_id}")
        return {"status": "success", "message": "Generations deleted successfully."}
    except Exception as e:
        logging.error(f"Error in delete_generations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    
class GenerationRequest(BaseModel):
    gen: str 
    element: int = Field(None, description="Element akUUID, e.g., 67297 for Jinx")
    generation_id: Optional[str] = Field(None, description="Optional generation ID for retries")
    
@router.post("/variant")
async def generate_and_poll_images(request: GenerationRequest):
    try:
        logging.info(f"Received generation request: {request}")
        if request.generation_id:
            try:
                logging.info(f"Deleting previous generation with ID: {request.generation_id}")
                delete_generation_api(request.generation_id)
            except Exception as e:
                logging.warning(f"Failed to delete previous generation {request.generation_id}: {e}")

        if request.element:
            create_response = create_asset_img(
                gen=request.gen,
                element=request.element,
            )
        else:
            create_response = create_asset_img(
                gen=request.gen,
            )
        generation_id = create_response["sdGenerationJob"]["generationId"]
        logging.info(f"Created new generation with ID: {generation_id}")

        # Poll for results
        for attempt in range(12):  # 12 attempts x 5s = 60s max
            try:
                images = get_generation(generation_id)
                if images:  
                    logging.info(f"Images found after {attempt + 1} attempts.")
                    return {"status": "success", "data": images, "gen": generation_id}
            except Exception as e:
                logging.warning(f"Polling attempt {attempt + 1} failed: {e}")

            await asyncio.sleep(5)  # Wait 5 seconds between polling attempts

        raise HTTPException(status_code=408, detail="Image generation timed out.")
    except Exception as e:
        logging.error(f"Error in generate_and_poll_images: {e}", exc_info=True)
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
            
        saved_result = await save_asset_with_image(asset, image_url)
        
        if saved_result.get("status") == "error":
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save asset: {saved_result.get('message')}"
            )
            
        return {
            "status": "success", 
            "asset": saved_result,
            "generation_id": generation_id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in generate_and_save_asset_image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


import logging
from fastapi import APIRouter, HTTPException
from services.leo import get_generation, delete_generation_api, create_asset_img
from services.generation import save_generation
from services.image_save import save_asset_with_image, download_image
from models.asset import AssetCreate
from models.generation import UsedAssets
import asyncio
from pydantic import BaseModel, Field
from typing import Optional, List
from bson import ObjectId

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


class UsedAssetRequest(BaseModel):
    id: str
    name: str
    type: str
    subcategory: str
    description: str
    image_data: str

class GenerationRequest(BaseModel):
    gen: str 
    element: int = Field(None, description="Element akUUID, e.g., 67297 for Jinx")
    generation_id: Optional[str] = Field(None, description="Optional generation ID for retries")
    weight: Optional[float] = Field(None, description="Weight for the generation")
    preset: Optional[str] = Field(None, description="Preset for the generation")
    description: Optional[str] = Field(None, description="Description for the generation")
    character_id: Optional[str] = Field(None, description="Character ID to associate with the generation")
    used_assets: Optional[List[UsedAssetRequest]] = Field(None, description="List of assets used in generation")
    

@router.post("/generation")
async def generate_and_save_gen_image(request: GenerationRequest):
    try:
        logger.info(f"Received gen-save request with gen: {request.gen}")
        logger.info(f"Used assets count: {len(request.used_assets) if request.used_assets else 0}")
        
        # Validate character_id if provided
        character_id = request.character_id
        if character_id and not ObjectId.is_valid(character_id):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid character_id format: {character_id}"
            )
        
        # Use default character_id if none provided
        if not character_id:
            character_id = "682cfdfaebbb3e6ada96d357"
        
        # Handle previous generation if needed
        if request.generation_id:
            try:
                logger.info(f"Deleting previous generation with ID: {request.generation_id}")
                delete_generation_api(request.generation_id)
            except Exception as e:
                logger.warning(f"Failed to delete previous generation {request.generation_id}: {e}")

        # Generate image
        create_response = create_asset_img(gen=request.gen, element=request.element, weight=request.weight, preset=request.preset)
        
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

        # Transform used assets to the proper format
        used_assets_transformed = None
        if request.used_assets:
            used_assets_transformed = [
                UsedAssets(
                    id=asset.id,
                    _id=asset.id,  # Set both for compatibility
                    name=asset.name,
                    type=asset.type,
                    subcategory=asset.subcategory,
                    description=asset.description,
                    image_data=asset.image_data,
                    url=f"/assets/image/{asset.id}"  # Generate URL for frontend
                )
                for asset in request.used_assets
            ]
            logger.info(f"Transformed {len(used_assets_transformed)} used assets")

        saved_result = await save_generation(
            character_id=character_id, 
            image_url=image_url,
            description=request.description,
            leo_id=generation_id,
            used_assets=used_assets_transformed
        )
        
        if saved_result.get("status") == "error":
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save generation: {saved_result.get('message')}"
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

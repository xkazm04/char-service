from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from bson import ObjectId
import os
from services.meshy import generate_3d_asset_from_image, get_image_to_3d_task_status
from database import generation_collection
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Meshy"],
)

class Image3DGenerationRequest(BaseModel):
    image_url: str
    generation_id: str  # Added generation_id
    prompt: Optional[str] = None

class Image3DGenerationResponse(BaseModel):
    model_url: str
    task_id: str
    status: str
    generation_id: str  # Added generation_id

class TextureInfo(BaseModel):
    base_color: Optional[str] = None
    metallic: Optional[str] = None
    normal: Optional[str] = None
    roughness: Optional[str] = None

class ModelStatusResponse(BaseModel):
    id: str
    model_urls: Optional[Dict[str, str]] = None
    thumbnail_url: Optional[str] = None
    texture_prompt: Optional[str] = None
    progress: int
    status: str
    texture_urls: Optional[List[TextureInfo]] = None
    task_error: Optional[Dict[str, Any]] = None
    generation_id: Optional[str] = None  # Added generation_id

@router.post("/", response_model=Image3DGenerationResponse)
async def create_3d_model(request: Image3DGenerationRequest):
    try:
        # Validate generation_id exists
        if not ObjectId.is_valid(request.generation_id):
            raise HTTPException(status_code=400, detail="Invalid generation_id format")
        
        generation = await generation_collection.find_one({"_id": ObjectId(request.generation_id)})
        if not generation:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        api_key = os.environ.get("MESHY_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="MESHY_API_KEY not found in environment variables")
        
        # Call the Meshy service
        response = generate_3d_asset_from_image(
            image_input=request.image_url,
            api_key=api_key,
            use_base64=False 
        )
        
        task_id = response.get("result", "")
        
        # Update generation with initial meshy data
        await generation_collection.update_one(
            {"_id": ObjectId(request.generation_id)},
            {
                "$set": {
                    "meshy": {
                        "meshy_id": task_id,
                        "glb_url": None,
                        "thumbnail_url": None,
                        "texture_prompt": None,
                        "texture_urls": None,
                        "task_error": None
                    }
                }
            }
        )
        
        logger.info(f"Started 3D generation for generation {request.generation_id} with task_id {task_id}")
        
        return {
            "model_url": "",  # Initially empty, will be populated when task completes
            "task_id": task_id,
            "status": "processing",
            "generation_id": request.generation_id
        }
    except Exception as e:
        logger.error(f"Error creating 3D model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}", response_model=ModelStatusResponse)
async def get_model_status(task_id: str, generation_id: Optional[str] = None):
    try:
        api_key = os.environ.get("MESHY_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="MESHY_API_KEY not found in environment variables")
        
        # Get task status from Meshy API
        response = get_image_to_3d_task_status(task_id, api_key)
        
        logger.info(f"Meshy API polled for task {task_id}")
        
        # Map the status from Meshy API format to our format
        status_mapping = {
            "SUCCEEDED": "completed",
            "FAILED": "failed",
            "PENDING": "processing",
            "PROCESSING": "processing"
        }
        
        mapped_status = status_mapping.get(response.get("status", ""), "processing")
        
        # Find the generation by meshy_id if generation_id is not provided
        generation_to_update = None
        if generation_id and ObjectId.is_valid(generation_id):
            generation_to_update = await generation_collection.find_one({"_id": ObjectId(generation_id)})
        else:
            # Find by meshy_id
            generation_to_update = await generation_collection.find_one({"meshy.meshy_id": task_id})
        
        # Update the database if task is completed and we found a generation
        if mapped_status == "completed" and generation_to_update:
            meshy_data = {
                "meshy_id": response.get("id", task_id),
                "glb_url": response.get("model_urls", {}).get("glb"),
                "fbx_url": response.get("model_urls", {}).get("fbx"),
                "usdz_url": response.get("model_urls", {}).get("usdz"),
                "obj_url": response.get("model_urls", {}).get("obj"),
                "thumbnail_url": response.get("thumbnail_url"),
                "texture_prompt": response.get("texture_prompt", ""),
                "texture_urls": response.get("texture_urls", []),
                "task_error": response.get("task_error"),
                "progress": response.get("progress", 100),
                "status": mapped_status
            }
            
            update_result = await generation_collection.update_one(
                {"_id": generation_to_update["_id"]},
                {"$set": {"meshy": meshy_data}}
            )
            
            if update_result.modified_count > 0:
                logger.info(f"Successfully updated generation {generation_to_update['_id']} with completed 3D model data")
                logger.info(f"Updated meshy data: {meshy_data}")
            else:
                logger.warning(f"No documents were modified when updating generation {generation_to_update['_id']}")
        elif mapped_status == "completed" and not generation_to_update:
            logger.warning(f"Completed task {task_id} but no generation found to update")
        elif mapped_status == "failed" and generation_to_update:
            # Update with error status
            error_data = {
                "meshy_id": response.get("id", task_id),
                "glb_url": None,
                "thumbnail_url": None,
                "texture_prompt": None,
                "texture_urls": None,
                "task_error": response.get("task_error", {"error": "Task failed"}),
                "progress": response.get("progress", 0),
                "status": "failed"
            }
            
            await generation_collection.update_one(
                {"_id": generation_to_update["_id"]},
                {"$set": {"meshy": error_data}}
            )
            
            logger.error(f"Updated generation {generation_to_update['_id']} with failed status")
        
        # Return the status with all relevant info
        return {
            "id": response.get("id", task_id),
            "model_urls": response.get("model_urls", {}),
            "thumbnail_url": response.get("thumbnail_url", ""),
            "texture_prompt": response.get("texture_prompt", ""),
            "progress": response.get("progress", 0),
            "status": mapped_status,
            "texture_urls": response.get("texture_urls", []),
            "task_error": response.get("task_error", {}),
            "generation_id": str(generation_to_update["_id"]) if generation_to_update else generation_id
        }
    except Exception as e:
        logger.error(f"Error getting model status for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


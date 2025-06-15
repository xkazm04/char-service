from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from bson import ObjectId
import os
from services.meshy import generate_3d_asset_from_image
from services.background_polling import meshy_polling_service
from database import generation_collection
from typing import Optional, Dict, List, Any
import logging
import requests

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Meshy"],
)

class Image3DGenerationRequest(BaseModel):
    image_url: str
    generation_id: str
    prompt: Optional[str] = None

class Image3DGenerationResponse(BaseModel):
    model_url: str
    task_id: str
    status: str
    generation_id: str

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
    generation_id: Optional[str] = None

@router.post("/", response_model=Image3DGenerationResponse)
async def create_3d_model(request: Image3DGenerationRequest):
    try:
        # Validate generation_id exists
        if not ObjectId.is_valid(request.generation_id):
            raise HTTPException(status_code=400, detail="Invalid generation_id format")
        
        generation = await generation_collection.find_one({"_id": ObjectId(request.generation_id)})
        if not generation:
            raise HTTPException(status_code=404, detail="Generation not found")
        from config import config
        api_key = config.meshy_api_key
        if not api_key:
            raise HTTPException(status_code=500, detail="MESHY_API_KEY not found in environment variables")
        
        # Call the Meshy service
        response = generate_3d_asset_from_image(
            image_input=request.image_url,
            api_key=api_key,
            use_base64=False 
        )
        
        task_id = response.get("result", "")
        
        # Update generation with initial meshy data and start background polling
        await generation_collection.update_one(
            {"_id": ObjectId(request.generation_id)},
            {
                "$set": {
                    "meshy": {
                        "meshy_id": task_id,
                        "glb_url": None,
                        "fbx_url": None,
                        "usdz_url": None,
                        "obj_url": None,
                        "thumbnail_url": None,
                        "texture_prompt": None,
                        "texture_urls": None,
                        "task_error": None,
                        "progress": 0,
                        "status": "processing",
                        "is_polling": True,
                        "last_polled": None,
                        "polling_attempts": 0
                    },
                    "is_3d_generating": True,
                    "has_3d_model": False
                }
            }
        )
        
        # Ensure polling service is running
        if not meshy_polling_service.is_running:
            await meshy_polling_service.start_polling()
        
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
        # Find the generation by meshy_id or generation_id
        generation_to_check = None
        if generation_id and ObjectId.is_valid(generation_id):
            generation_to_check = await generation_collection.find_one({"_id": ObjectId(generation_id)})
        else:
            # Find by meshy_id
            generation_to_check = await generation_collection.find_one({"meshy.meshy_id": task_id})
        
        if not generation_to_check:
            raise HTTPException(status_code=404, detail="Generation not found")
            
        meshy_data = generation_to_check.get("meshy", {})
        
        # Return current status from database (updated by background polling)
        return {
            "id": meshy_data.get("meshy_id", task_id),
            "model_urls": {
                "glb": meshy_data.get("glb_url"),
                "fbx": meshy_data.get("fbx_url"),
                "usdz": meshy_data.get("usdz_url"),
                "obj": meshy_data.get("obj_url")
            },
            "thumbnail_url": meshy_data.get("thumbnail_url", ""),
            "texture_prompt": meshy_data.get("texture_prompt", ""),
            "progress": meshy_data.get("progress", 0),
            "status": meshy_data.get("status", "processing"),
            "texture_urls": meshy_data.get("texture_urls", []),
            "task_error": meshy_data.get("task_error", {}),
            "generation_id": str(generation_to_check["_id"])
        }
    except Exception as e:
        logger.error(f"Error getting model status for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/proxy/{task_id}/{file_type}")
async def proxy_model_file(task_id: str, file_type: str):
    """
    Proxy 3D model files from Meshy to avoid CORS issues.
    file_type can be: glb, fbx, usdz, obj, thumbnail
    """
    try:
        # Get the generation with the meshy data
        generation = await generation_collection.find_one({"meshy.meshy_id": task_id})
        if not generation or "meshy" not in generation:
            raise HTTPException(status_code=404, detail="Model not found")
        
        meshy_data = generation["meshy"]
        
        # Get the appropriate URL based on file_type
        url_mapping = {
            "glb": meshy_data.get("glb_url"),
            "fbx": meshy_data.get("fbx_url"),
            "usdz": meshy_data.get("usdz_url"),
            "obj": meshy_data.get("obj_url"),
            "thumbnail": meshy_data.get("thumbnail_url")
        }
        
        model_url = url_mapping.get(file_type)
        if not model_url:
            raise HTTPException(status_code=404, detail=f"File type {file_type} not available")
        
        # Fetch the file from Meshy
        response = requests.get(model_url, stream=True)
        response.raise_for_status()
        
        # Determine content type
        content_type_mapping = {
            "glb": "model/gltf-binary",
            "fbx": "application/octet-stream",
            "usdz": "model/vnd.usdz+zip",
            "obj": "application/object",
            "thumbnail": "image/jpeg"
        }
        
        content_type = content_type_mapping.get(file_type, "application/octet-stream")
        
        # Return the file with proper headers
        return StreamingResponse(
            iter([response.content]),
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except requests.RequestException as e:
        logger.error(f"Error fetching model file: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch model file")
    except Exception as e:
        logger.error(f"Error proxying model file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
from services.meshy import generate_3d_asset_from_image, get_image_to_3d_task_status
from typing import Optional, Dict, List, Any

router = APIRouter(
    tags=["Meshy"],
)

class Image3DGenerationRequest(BaseModel):
    image_url: str
    prompt: Optional[str] = None

class Image3DGenerationResponse(BaseModel):
    model_url: str
    task_id: str
    status: str

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

@router.post("/", response_model=Image3DGenerationResponse)
async def create_3d_model(request: Image3DGenerationRequest):
    try:
        api_key = os.environ.get("MESHY_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="MESHY_API_KEY not found in environment variables")
        
        # Call the Meshy service
        response = generate_3d_asset_from_image(
            image_input=request.image_url,
            api_key=api_key,
            use_base64=False 
        )
        return {
            "model_url": response.get("model_urls", {}).get("glb", "") if response.get("model_urls") else "",
            "task_id": response.get("id", ""),
            "status": "processing" if response.get("status") != "SUCCEEDED" else "completed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}", response_model=ModelStatusResponse)
async def get_model_status(task_id: str):
    try:
        # Get API key from environment variable
        api_key = os.environ.get("MESHY_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="MESHY_API_KEY not found in environment variables")
        
        # Get task status from Meshy API
        response = get_image_to_3d_task_status(task_id, api_key)
        
        # Map the status from Meshy API format to our format
        status_mapping = {
            "SUCCEEDED": "completed",
            "FAILED": "failed",
            "PENDING": "processing",
            "PROCESSING": "processing"
        }
        
        # Return the status with all relevant info
        return {
            "id": response.get("id", task_id),
            "model_urls": response.get("model_urls", {}),
            "thumbnail_url": response.get("thumbnail_url", ""),
            "texture_prompt": response.get("texture_prompt", ""),
            "progress": response.get("progress", 0),
            "status": status_mapping.get(response.get("status", ""), "processing"),
            "texture_urls": response.get("texture_urls", []),
            "task_error": response.get("task_error", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


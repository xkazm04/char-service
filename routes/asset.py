from fastapi import APIRouter, Body, HTTPException, status, Form, Response
from fastapi.responses import JSONResponse
from typing import List, Optional
import json
from services.image_analyze import analyze_image, analyze_with_gemini
from services.image_save import  serialize_for_json
from services.asset_save import save_asset_with_vector, validate_asset
from fastapi import UploadFile, File
from models.asset import AssetCreate, AssetResponse
from database import asset_collection
import logging
from pydantic import BaseModel
import asyncio
from bson import ObjectId
from utils.db_helpers import serialize_for_json

router = APIRouter()

logging.basicConfig(level=logging.INFO)


class ModelConfig(BaseModel):
    enabled: bool
    apiKey: Optional[str] = None

class AnalysisConfig(BaseModel):
    openai: ModelConfig
    gemini: ModelConfig
    groq: ModelConfig

@router.get("/", response_model=List[AssetResponse])
async def get_assets():
    """
    Get all assets from the database
    """
    assets = await asset_collection.find().to_list(1000)
    serialized_assets = []
    
    for asset in assets:
        asset_dict = serialize_for_json(dict(asset))
        
        # Remove binary image data and large embeddings from response
        if "image_data" in asset_dict:
            if asset.get("image_data") is not None:
                asset_dict["image_data_size"] = len(asset["image_data"])
            else:
                asset_dict["image_data_size"] = 0
            del asset_dict["image_data"]
        
        if "description_vector" in asset_dict:
            del asset_dict["description_vector"]
        
        if "image_embedding" in asset_dict:
            del asset_dict["image_embedding"]
        
        if "_id" in asset_dict and "id" not in asset_dict:
            asset_dict["id"] = asset_dict["_id"]
            
        serialized_assets.append(asset_dict)
            
    return JSONResponse(content=serialized_assets)

@router.get("/{id}", response_model=AssetResponse)
async def get_asset(id: str):
    """
    Get a specific asset by ID
    """
    try:
        object_id = ObjectId(id)
        if (asset := await asset_collection.find_one({"_id": object_id})) is not None:
            # Convert to serializable dictionary
            serialized_asset = serialize_for_json(dict(asset))

            if "image_data" in serialized_asset:
                if asset.get("image_data") is not None:
                    serialized_asset["image_data_size"] = len(asset["image_data"])
                else:
                    serialized_asset["image_data_size"] = 0
                del serialized_asset["image_data"]
            
            if "description_vector" in serialized_asset:
                del serialized_asset["description_vector"]
            
            if "image_embedding" in serialized_asset:
                del serialized_asset["image_embedding"]
            
            # Make sure id field exists
            if "_id" in serialized_asset and "id" not in serialized_asset:
                serialized_asset["id"] = serialized_asset["_id"]
                
            return JSONResponse(content=serialized_asset)
    except:
        pass
    
    raise HTTPException(status_code=404, detail=f"Asset with id {id} not found")

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(id: str):
    """
    Delete an asset by ID
    """
    try:
        object_id = ObjectId(id)
        delete_result = await asset_collection.delete_one({"_id": object_id})
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Asset with ID {id} not found")
        return None 
    except Exception as e:
        logging.error(f"Error deleting asset with ID {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid ID format or deletion error: {str(e)}")

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset: AssetCreate = Body(...)):
    """
    Create a new asset
    """
    try:
        description_vector = None
        asset_dict = asset.model_dump()
        
        if "description_vector" in asset_dict:
            description_vector = asset_dict.pop("description_vector")
        
        clean_asset = AssetCreate(**asset_dict)
        result = await save_asset_with_vector(clean_asset, description_vector)
        
        # Check if save was successful
        if result.get("status") == "saved":
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=result
            )
        elif result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
        else:
            raise HTTPException(status_code=500, detail="Unexpected response from save operation")
            
    except Exception as e:
        logging.error(f"Error creating asset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating asset: {str(e)}")

@router.post("/validate", status_code=status.HTTP_200_OK)
async def validate_asset_vector(asset: AssetCreate = Body(...)):
    """
    Validate an asset by checking for similar existing assets
    Returns embedding vector and similar assets if found
    """
    try:
        api_key = None  
        result = await validate_asset(asset, api_key)
        
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except Exception as e:
        logging.error(f"Error validating asset: {e}")
        raise HTTPException(status_code=500, detail=f"Error validating asset: {str(e)}")

@router.post("/analyze")
async def analyze_asset_image(
    file: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Analyze an uploaded image using selected models based on configuration.
    Config parameter specifies which models to use and provides API keys if needed.
    """
    # Save uploaded file to a temporary location
    contents = await file.read()
    logging.info(f"Received file: {file.filename} of size {len(contents)} bytes")
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)
    
    logging.info(f"Saved file to temporary path: {temp_path}")

    try:
        config_dict = json.loads(config)
        analysis_config = AnalysisConfig(**config_dict)
    except Exception as e:
        logging.error(f"Error parsing configuration: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration format: {str(e)}")
    
    # Ensure at least one model is enabled
    if not any([analysis_config.openai.enabled, analysis_config.gemini.enabled, analysis_config.groq.enabled]):
        raise HTTPException(status_code=400, detail="At least one model must be enabled")
    
    # Set up tasks based on enabled models
    tasks = []
    async def run_blocking(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    results = {
        "groq": [],
        "openai": [],
        "gemini": []
    }
    
    if analysis_config.groq.enabled:
        api_key = analysis_config.groq.apiKey if analysis_config.groq.apiKey else None
        tasks.append(("groq", run_blocking(analyze_image, temp_path, "groq", api_key)))
    
    if analysis_config.openai.enabled:
        api_key = analysis_config.openai.apiKey if analysis_config.openai.apiKey else None
        tasks.append(("openai", run_blocking(analyze_image, temp_path, "openai", api_key)))
    
    if analysis_config.gemini.enabled:
        api_key = analysis_config.gemini.apiKey if analysis_config.gemini.apiKey else None
        tasks.append(("gemini", run_blocking(analyze_with_gemini, temp_path, api_key)))
    
    try:
        # Execute enabled model analysis tasks
        for model_name, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=120)
                # Ensure result is a list
                if isinstance(result, list):
                    results[model_name] = result
                elif isinstance(result, dict) and not result:
                    results[model_name] = []
                elif isinstance(result, dict):
                    # Try to convert dict to list if needed
                    if any(isinstance(v, list) for v in result.values()):
                        for v in result.values():
                            if isinstance(v, list):
                                results[model_name] = v
                                break
                    else:
                        results[model_name] = [result]
                else:
                    results[model_name] = []
                    logging.warning(f"Unexpected result type from {model_name}: {type(result)}")
            except Exception as e:
                logging.error(f"{model_name.capitalize()} analysis failed: {e}")
                results[model_name] = []
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Image analysis timed out")
    except Exception as e:
        logging.error(f"Unexpected error during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error during image analysis: {str(e)}")

    return results


@router.get("/image/{asset_id}")
async def get_asset_image(asset_id: str):
    try:
        if not ObjectId.is_valid(asset_id):
            raise HTTPException(status_code=400, detail="Invalid asset ID format")
            
        asset = await asset_collection.find_one({"_id": ObjectId(asset_id)})
        
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
            
        if "image_data" not in asset or not asset["image_data"]:
            raise HTTPException(status_code=404, detail="Asset has no image data")
            
        content_type = "image/jpeg"
        
        return Response(
            content=asset["image_data"], 
            media_type=content_type
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving asset image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
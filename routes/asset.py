from fastapi import APIRouter, Body, HTTPException, status, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import json
from services.image_analyze import analyze_image, analyze_with_gemini
from services.image_save import validate_asset, save_asset_with_vector, serialize_for_json
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
    serialized_assets = [serialize_for_json(dict(asset)) for asset in assets]
    
    for asset in serialized_assets:
        if "_id" in asset and "id" not in asset:
            asset["id"] = asset["_id"]
            
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
        # Extract vector if provided in request
        description_vector = None
        asset_dict = asset.model_dump()
        
        if "description_vector" in asset_dict:
            description_vector = asset_dict.pop("description_vector")
        
        # Create a new AssetCreate instance without the vector
        clean_asset = AssetCreate(**asset_dict)
        
        # Save asset with vector
        result = await save_asset_with_vector(clean_asset, description_vector)
        
        # Check if save was successful
        if result.get("status") == "saved":
            # The result is already serialized by our improved save_asset_with_vector function
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=result
            )
        elif result.get("status") == "error":
            # Return detailed error from save function
            raise HTTPException(status_code=500, detail=result.get("message", "Unknown error"))
        else:
            # Unexpected result status
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
    
    # Parse the configuration
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
                    # Empty dict should be an empty list
                    results[model_name] = []
                elif isinstance(result, dict):
                    # Try to convert dict to list if needed
                    if any(isinstance(v, list) for v in result.values()):
                        # Get the first list in the dict
                        for v in result.values():
                            if isinstance(v, list):
                                results[model_name] = v
                                break
                    else:
                        # Wrap single dict in a list
                        results[model_name] = [result]
                else:
                    # Fallback for any other case
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
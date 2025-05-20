from fastapi import APIRouter, Body, HTTPException, status, Form, Response, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from services.image_analyze import analyze_image, analyze_with_gemini
from services.asset_save import save_asset_with_vector, validate_asset
from fastapi import UploadFile, File
from models.asset import AssetCreate, AssetResponse, PaginatedAssetResponse, AssetDB
from database import asset_collection
from pydantic import BaseModel
from bson import ObjectId
import base64
import math
import logging
import io # For in-memory byte streams
from PIL import Image # For image manipulation

router = APIRouter()

logging.basicConfig(level=logging.INFO)


class ModelConfig(BaseModel):
    enabled: bool
    apiKey: Optional[str] = None

class AnalysisConfig(BaseModel):
    openai: ModelConfig
    gemini: ModelConfig
    groq: ModelConfig

@router.get("/", response_model=PaginatedAssetResponse)
async def get_assets(
    type: Optional[str] = Query(None, description="Filter assets by type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of assets per page"),
    image_quality: int = Query(20, ge=10, le=95, description="Image quality for JPEGs (10-95)"),
    max_image_width: Optional[int] = Query(None, ge=60, description="Maximum width for resized images")
):
    """
    Get assets from the database with pagination and optional type filtering.
    Includes Base64 encoded image data, potentially re-compressed or resized.
    """
    query_filter = {}
    if type:
        query_filter["type"] = type

    skip_amount = (page - 1) * page_size
    
    total_assets_count = await asset_collection.count_documents(query_filter)
    if total_assets_count == 0:
        return PaginatedAssetResponse(
            assets=[],
            total_assets=0,
            total_pages=0,
            current_page=page,
            page_size=page_size
        )

    total_pages = math.ceil(total_assets_count / page_size)

    # Select only necessary fields from DB initially, especially if image_data is large
    # and you decide to process it. If image_data is always processed, fetching it is fine.
    assets_cursor = asset_collection.find(query_filter).skip(skip_amount).limit(page_size)
    
    processed_assets: List[AssetResponse] = []
    async for asset_doc_raw in assets_cursor:
        try:
            asset_data_for_response = dict(asset_doc_raw)

            if asset_doc_raw.get("image_data") and isinstance(asset_doc_raw["image_data"], bytes):
                original_image_bytes = asset_doc_raw["image_data"]
                content_type = asset_doc_raw.get("contentType", "image/png") # Default to PNG if not specified

                try:
                    img = Image.open(io.BytesIO(original_image_bytes))
                    
                    # Determine format for saving (e.g., JPEG, PNG)
                    # Use the original content type to guide the save format if possible
                    save_format = 'JPEG' # Default to JPEG for better compression control
                    if content_type.lower() == "image/png":
                        save_format = 'PNG'
                    elif content_type.lower() == "image/webp":
                        save_format = 'WEBP'
                    # Add more formats if needed

                    # Resize if max_image_width is specified
                    if max_image_width and img.width > max_image_width:
                        aspect_ratio = img.height / img.width
                        new_height = int(max_image_width * aspect_ratio)
                        img = img.resize((max_image_width, new_height), Image.Resampling.LANCZOS)

                    output_buffer = io.BytesIO()
                    if save_format == 'JPEG':
                        # For JPEGs, ensure image is in RGB mode (strips alpha)
                        if img.mode in ('RGBA', 'LA', 'P'): # P is for paletted images
                            img = img.convert('RGB')
                        img.save(output_buffer, format=save_format, quality=image_quality, optimize=True)
                        # Update content type if we converted to JPEG
                        asset_data_for_response["image_content_type"] = "image/jpeg"
                    elif save_format == 'PNG':
                        img.save(output_buffer, format=save_format, optimize=True)
                        asset_data_for_response["image_content_type"] = "image/png"
                    elif save_format == 'WEBP':
                        img.save(output_buffer, format=save_format, quality=image_quality) # WEBP also uses quality
                        asset_data_for_response["image_content_type"] = "image/webp"
                    else: # Fallback for other types or if original format is preferred
                        img.save(output_buffer, format=img.format or 'PNG') # Use original format or default to PNG
                        asset_data_for_response["image_content_type"] = content_type # Keep original or detected

                    compressed_image_bytes = output_buffer.getvalue()
                    asset_data_for_response["image_data_base64"] = base64.b64encode(compressed_image_bytes).decode('utf-8')
                
                except Exception as img_e:
                    logging.warning(f"Could not process image for asset {asset_doc_raw.get('_id')}: {img_e}. Using original.")
                    # Fallback to original if processing fails
                    asset_data_for_response["image_data_base64"] = base64.b64encode(original_image_bytes).decode('utf-8')
                    asset_data_for_response["image_content_type"] = content_type
            
            asset_data_for_response.pop("description_vector", None)
            asset_data_for_response.pop("image_embedding", None)
            asset_data_for_response.pop("image_data", None) # Remove original raw bytes

            asset_resp = AssetResponse.model_validate(asset_data_for_response)
            processed_assets.append(asset_resp)

        except Exception as e:
            logging.error(f"Error processing asset {asset_doc_raw.get('_id')}: {e}")
            continue # Skip this asset or handle error appropriately

    return PaginatedAssetResponse(
        assets=processed_assets,
        total_assets=total_assets_count,
        total_pages=total_pages,
        current_page=page,
        page_size=page_size
    )

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
        
        if result.get("status") == "saved":
            if "description_vector" in result:
                del result["description_vector"]
                
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
    Returns similar assets if found but omits embedding vector
    """
    try:
        api_key = None  
        result = await validate_asset(asset, api_key)
        
        if "description_vector" in result:
            del result["description_vector"]
            
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
    
    if not any([analysis_config.openai.enabled, analysis_config.gemini.enabled, analysis_config.groq.enabled]):
        raise HTTPException(status_code=400, detail="At least one model must be enabled")
    
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
        for model_name, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=120)
                if isinstance(result, list):
                    results[model_name] = result
                elif isinstance(result, dict) and not result:
                    results[model_name] = []
                elif isinstance(result, dict):
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
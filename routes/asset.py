from fastapi import APIRouter, Body, HTTPException, status, Response, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from services.asset_save import save_asset_with_vector, validate_asset, validate_asset_hybrid
from models.asset import AssetCreate, AssetResponse, PaginatedAssetResponse
from database import asset_collection
from pydantic import BaseModel
from bson import ObjectId
import base64
import math
import logging
import io
from PIL import Image
import asyncio
from datetime import datetime
from utils.cached_batch import generate_cache_key, get_cached_batch, set_cached_batch

router = APIRouter()
logging.basicConfig(level=logging.INFO)

cache_collection = None  

class AssetBatchResponse(BaseModel):
    assets: List[AssetResponse]
    batch_id: str
    total_assets: int
    total_pages: int
    current_page: int
    page_size: int
    cache_key: str


@router.get("/batched", response_model=AssetBatchResponse)
async def get_assets_batched(
    type: Optional[str] = Query(None, description="Filter assets by type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Number of assets per page"),
    image_quality: int = Query(20, ge=10, le=95, description="Image quality for JPEGs (10-95)"),
    max_image_width: Optional[int] = Query(None, ge=60, description="Maximum width for resized images")
):
    """
    Get assets with improved caching and batching for better performance
    """
    cache_key = generate_cache_key(type, page, page_size, image_quality, max_image_width)
    
    # Try to get from cache first
    cached_data = await get_cached_batch(cache_key, cache_collection)
    if cached_data:
        return AssetBatchResponse(**cached_data)
    
    query_filter = {}
    if type:
        query_filter["type"] = type

    skip_amount = (page - 1) * page_size
    
    # Use aggregation pipeline for better performance
    pipeline = [
        {"$match": query_filter},
        {"$facet": {
            "data": [
                {"$skip": skip_amount},
                {"$limit": page_size},
                {"$project": {
                    "_id": 1,
                    "name": 1,
                    "type": 1,
                    "subcategory": 1,
                    "gen": 1,
                    "description": 1,
                    "image_url": 1,
                    "image_data": 1,
                    "contentType": 1,
                    "created_at": 1
                }}
            ],
            "count": [
                {"$count": "total"}
            ]
        }}
    ]
    
    result = await asset_collection.aggregate(pipeline).to_list(1)
    
    if not result or not result[0]["data"]:
        empty_response = {
            "assets": [],
            "batch_id": f"batch_{page}_{cache_key[:8]}",
            "total_assets": 0,
            "total_pages": 0,
            "current_page": page,
            "page_size": page_size,
            "cache_key": cache_key
        }
        await set_cached_batch(cache_key, empty_response)
        return AssetBatchResponse(**empty_response)
    
    assets_data = result[0]["data"]
    total_assets_count = result[0]["count"][0]["total"] if result[0]["count"] else 0
    total_pages = math.ceil(total_assets_count / page_size)
    
    # Process images in parallel
    async def process_asset_image(asset_doc_raw):
        try:
            asset_data_for_response = dict(asset_doc_raw)
            
            if asset_doc_raw.get("image_data") and isinstance(asset_doc_raw["image_data"], bytes):
                # Process image in executor to avoid blocking
                loop = asyncio.get_event_loop()
                processed_image = await loop.run_in_executor(
                    None, 
                    process_image_sync, 
                    asset_doc_raw["image_data"],
                    asset_doc_raw.get("contentType", "image/png"),
                    image_quality,
                    max_image_width
                )
                
                if processed_image:
                    asset_data_for_response["image_data_base64"] = processed_image["base64"]
                    asset_data_for_response["image_content_type"] = processed_image["content_type"]
            
            # Remove unnecessary fields
            for field in ["description_vector", "image_embedding", "image_data"]:
                asset_data_for_response.pop(field, None)
            
            return AssetResponse.model_validate(asset_data_for_response)
        except Exception as e:
            logging.error(f"Error processing asset {asset_doc_raw.get('_id')}: {e}")
            return None
    
    # Process all assets concurrently
    processed_assets = await asyncio.gather(
        *[process_asset_image(asset) for asset in assets_data],
        return_exceptions=True
    )
    
    # Filter out failed processing results
    valid_assets = [asset for asset in processed_assets if isinstance(asset, AssetResponse)]
    
    response_data = {
        "assets": valid_assets,
        "batch_id": f"batch_{page}_{cache_key[:8]}",
        "total_assets": total_assets_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "cache_key": cache_key
    }
    
    # Cache the response
    await set_cached_batch(cache_key, response_data)
    
    return AssetBatchResponse(**response_data)

def process_image_sync(image_bytes: bytes, content_type: str, quality: int, max_width: Optional[int]) -> Optional[dict]:
    """Synchronous image processing function for executor"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        save_format = 'JPEG'
        if content_type.lower() == "image/png":
            save_format = 'PNG'
        elif content_type.lower() == "image/webp":
            save_format = 'WEBP'
        
        # Resize if needed
        if max_width and img.width > max_width:
            aspect_ratio = img.height / img.width
            new_height = int(max_width * aspect_ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        output_buffer = io.BytesIO()
        if save_format == 'JPEG':
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.save(output_buffer, format=save_format, quality=quality, optimize=True)
            final_content_type = "image/jpeg"
        elif save_format == 'PNG':
            img.save(output_buffer, format=save_format, optimize=True)
            final_content_type = "image/png"
        elif save_format == 'WEBP':
            img.save(output_buffer, format=save_format, quality=quality)
            final_content_type = "image/webp"
        else:
            img.save(output_buffer, format=img.format or 'PNG')
            final_content_type = content_type
        
        compressed_image_bytes = output_buffer.getvalue()
        return {
            "base64": base64.b64encode(compressed_image_bytes).decode('utf-8'),
            "content_type": final_content_type
        }
    except Exception as e:
        logging.warning(f"Image processing failed: {e}")
        return None

# Keep the original endpoint for backward compatibility
@router.get("/", response_model=PaginatedAssetResponse)
async def get_assets(
    type: Optional[str] = Query(None, description="Filter assets by type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of assets per page"),
    image_quality: int = Query(20, ge=10, le=95, description="Image quality for JPEGs (10-95)"),
    max_image_width: Optional[int] = Query(None, ge=60, description="Maximum width for resized images")
):
    """Original endpoint - redirects to batched version"""
    batched_response = await get_assets_batched(type, page, page_size, image_quality, max_image_width)
    
    # Remove image_data_base64 from the response
    for asset in batched_response.assets:
        if hasattr(asset, 'image_data_base64'):
            del asset.image_data_base64
    
    return PaginatedAssetResponse(
        assets=batched_response.assets,
        total_assets=batched_response.total_assets,
        total_pages=batched_response.total_pages,
        current_page=batched_response.current_page,
        page_size=batched_response.page_size
    )

@router.post("/cache/invalidate")
async def invalidate_cache(type_filter: Optional[str] = None):
    """Invalidate cache for specific type or all cache"""
    try:
        if cache_collection is None:
            raise HTTPException(status_code=500, detail="Cache not configured")
        
        query = {}
        if type_filter:
            # Invalidate cache entries that match the type filter pattern
            query = {"cache_key": {"$regex": f"^{type_filter}_"}}
        
        result = await cache_collection.delete_many(query)
        
        return {
            "status": "success",
            "deleted_entries": result.deleted_count,
            "message": f"Cache invalidated for {'all entries' if not type_filter else f'type: {type_filter}'}"
        }
    except Exception as e:
        logging.error(f"Cache invalidation error: {e}")
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {e}")

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
async def validate_asset_vector(
    asset: AssetCreate = Body(...),
    use_atlas_search: bool = Query(False, description="Use enhanced Atlas Vector Search")
):
    """
    Validate an asset by checking for similar existing assets.
    Now supports both original method and enhanced Atlas Vector Search.
    """
    try:
        if use_atlas_search:
            result = await validate_asset_hybrid(asset, use_atlas_search=True)
        else:
            api_key = None  
            result = await validate_asset(asset, api_key)
        
        # Remove description_vector before returning to frontend
        if "description_vector" in result:
            del result["description_vector"]
            
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)
    except Exception as e:
        logging.error(f"Error validating asset: {e}")
        raise HTTPException(status_code=500, detail=f"Error validating asset: {str(e)}")


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
    

@router.patch("/{id}", response_model=AssetResponse)
async def update_asset(id: str, updates: dict = Body(...)):
    """
    Update an asset by ID with partial data
    """
    try:
        object_id = ObjectId(id)
        
        # Remove any fields that shouldn't be updated directly
        forbidden_fields = ['_id', 'created_at', 'description_vector', 'image_embedding']
        clean_updates = {k: v for k, v in updates.items() if k not in forbidden_fields}
        
        if not clean_updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        # Add updated timestamp
        clean_updates['updated_at'] = datetime.utcnow()
        
        # Update the asset
        update_result = await asset_collection.update_one(
            {"_id": object_id},
            {"$set": clean_updates}
        )
        
        if update_result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"Asset with ID {id} not found")
        
        # Fetch and return the updated asset
        updated_asset = await asset_collection.find_one({"_id": object_id})
        if not updated_asset:
            raise HTTPException(status_code=404, detail="Asset not found after update")
        
        # Remove sensitive fields before returning
        for field in ["description_vector", "image_embedding", "image_data"]:
            updated_asset.pop(field, None)
        
        return AssetResponse.model_validate(updated_asset)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating asset with ID {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid ID format or update error: {str(e)}")


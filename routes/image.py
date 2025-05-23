from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
import zipfile
import io
from bson import ObjectId
from PIL import Image
import json
import base64
import asyncio
from concurrent.futures import ThreadPoolExecutor
from database import asset_collection
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Option 1: ZIP Archive of Images
@router.get("/images/batch/zip")
async def get_images_batch_zip(
    asset_ids: str = Query(..., description="Comma-separated asset IDs"),
    size: Optional[str] = Query("thumbnail", description="Size: thumbnail, small, medium, large, full"),
    format: str = Query("jpeg", description="Image format: jpeg, png, webp")
):
    """
    Download multiple images as a ZIP archive
    """
    ids = [id.strip() for id in asset_ids.split(",") if id.strip()]
    
    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 images per request")
    
    # Size mapping
    size_params = {
        "thumbnail": {"width": 150, "quality": 70},
        "small": {"width": 300, "quality": 75},
        "medium": {"width": 600, "quality": 80},
        "large": {"width": 1200, "quality": 85},
        "full": {"quality": 90}
    }
    
    params = size_params.get(size, size_params["medium"])
    
    async def create_zip():
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            async for asset_id in asyncio.as_completed([
                get_single_image_data(asset_id, params, format) for asset_id in ids
            ]):
                try:
                    image_data, filename = await asset_id
                    if image_data:
                        zip_file.writestr(filename, image_data)
                except Exception as e:
                    logging.error(f"Error processing image in batch: {e}")
                    continue
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    zip_data = await create_zip()
    
    return StreamingResponse(
        io.BytesIO(zip_data),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=images_batch.zip"}
    )


# Option 3: Streaming Multiple Images
@router.get("/images/batch/stream")
async def stream_images_batch(
    asset_ids: str = Query(..., description="Comma-separated asset IDs"),
    size: str = Query("medium", description="Image size")
):
    """
    Stream multiple images in multipart response
    """
    ids = [id.strip() for id in asset_ids.split(",") if id.strip()]
    
    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 images per request")
    
    async def generate_multipart():
        boundary = "----ImageBatchBoundary"
        
        for asset_id in ids:
            try:
                image_data, filename = await get_single_image_data(asset_id, {"width": 600}, "jpeg")
                if image_data:
                    yield f"--{boundary}\r\n".encode()
                    yield f"Content-Type: image/jpeg\r\n".encode()
                    yield f"Content-Disposition: attachment; filename=\"{filename}\"\r\n".encode()
                    yield f"X-Asset-ID: {asset_id}\r\n\r\n".encode()
                    yield image_data
                    yield b"\r\n"
            except Exception as e:
                logging.error(f"Error streaming image {asset_id}: {e}")
                continue
        
        yield f"--{boundary}--\r\n".encode()
    
    return StreamingResponse(
        generate_multipart(),
        media_type=f"multipart/mixed; boundary=----ImageBatchBoundary"
    )

async def get_single_image_data(asset_id: str, params: dict, format: str) -> tuple:
    """Helper function to get processed image data"""
    try:
        if not ObjectId.is_valid(asset_id):
            return None, None
            
        asset = await asset_collection.find_one({"_id": ObjectId(asset_id)})
        
        if not asset or "image_data" not in asset:
            return None, None
        
        image_data = asset["image_data"]
        filename = f"{asset_id}.{format}"
        
        # Process image with params
        if params:
            img = Image.open(io.BytesIO(image_data))
            
            # Resize if width specified
            if "width" in params:
                width = params["width"]
                ratio = width / img.width
                height = int(img.height * ratio)
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            # Convert format and quality
            output_buffer = io.BytesIO()
            if format.lower() == "jpeg":
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(output_buffer, format='JPEG', quality=params.get("quality", 85), optimize=True)
            elif format.lower() == "png":
                img.save(output_buffer, format='PNG', optimize=True)
            elif format.lower() == "webp":
                img.save(output_buffer, format='WEBP', quality=params.get("quality", 85))
            
            image_data = output_buffer.getvalue()
        
        return image_data, filename
        
    except Exception as e:
        logging.error(f"Error processing image {asset_id}: {e}")
        return None, None
from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List
import asyncio
from services.image_analyze import analyze_image, analyze_with_gemini
from fastapi import UploadFile, File
from models.asset import AssetCreate, AssetResponse, AssetDB
from database import asset_collection
import logging
router = APIRouter()

logging.basicConfig(level=logging.INFO)

@router.get("/", response_model=List[AssetResponse])
async def get_assets():
    """
    Get all assets from the database
    """
    assets = await asset_collection.find().to_list(1000)
    return assets

@router.get("/{id}", response_model=AssetResponse)
async def get_asset(id: str):
    """
    Get a specific asset by ID
    """
    if (asset := await asset_collection.find_one({"_id": id})) is not None:
        return asset
    
    raise HTTPException(status_code=404, detail=f"Asset with id {id} not found")

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset: AssetCreate = Body(...)):
    """
    Create a new asset
    """
    asset = jsonable_encoder(AssetDB(**asset.dict()))
    new_asset = await asset_collection.insert_one(asset)
    created_asset = await asset_collection.find_one({"_id": new_asset.inserted_id})
    
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_asset)

@router.post("/analyze", response_model=List[dict])
async def analyze_asset_image(file: UploadFile = File(...)):
    """
    Analyze an uploaded image using both OpenAI and Gemini models in parallel.
    Waits up to 60 seconds for both results and returns them as an array.
    """
    # Save uploaded file to a temporary location
    contents = await file.read()
    logging.info(f"Received file: {file.filename} of size {len(contents)} bytes")
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)

    logging.info(f"Saved file to temporary path: {temp_path}")
    async def run_blocking(func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                run_blocking(analyze_image, temp_path),
                run_blocking(analyze_with_gemini, temp_path)
            ),
            timeout=120
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Image analysis timed out")

    return results
from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List

from models.asset import AssetCreate, AssetResponse, AssetDB
from database import asset_collection

router = APIRouter()

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

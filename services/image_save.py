import logging
from openai import OpenAI
import os
import requests
from typing import List, Dict, Any, Optional, Tuple
from models.asset import AssetCreate, AssetDB
from database import asset_collection
from utils.db_helpers import serialize_for_json
import base64
from services.asset_save import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

async def get_image_embedding(image_data: bytes, api_key: Optional[str] = None) -> List[float]:
    """
    Generate embeddings for an image using OpenAI's CLIP model
    """
    try:
        client = OpenAI(api_key=api_key or OPENAI_API_KEY)
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        )
        
        embedding = response.data[0].embedding
        return embedding
        
    except Exception as e:
        logger.error(f"Error generating image embedding: {e}")
        return [0.0] * 1536  # Adjust default size if using a different model

async def download_image(url: str) -> Tuple[bytes, Optional[str]]:
    """
    Download an image from a URL and return the binary data
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '')

        if len(response.content) > 10 * 1024 * 1024:
            logger.warning(f"Image is too large: {len(response.content) / (1024 * 1024):.2f} MB")
            raise ValueError("Image is too large (>10MB)")
            
        return response.content, content_type
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        raise

async def save_asset_with_image(
    asset: AssetCreate, 
    image_url: str, 
    description_embedding: Optional[List[float]] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Download image from URL and save asset with image binary data.
    We'll skip the image embedding for now.
    """
    try:
        logger.info(f"Starting save_asset_with_image for asset: {asset.name}")
        
        if description_embedding is None:
            text_to_embed = f"{asset.name} {asset.description or ''}"
            description_embedding = await get_embedding(text_to_embed, api_key)
        
        # Download the image
        logger.info(f"Downloading image from URL: {image_url}")
        image_data, content_type = await download_image(image_url)
        logger.info(f"Downloaded image of type: {content_type}, size: {len(image_data) / 1024:.2f} KB")
        
        image_embedding = []
        
        asset_dict = asset.model_dump(exclude={
            "description_vector", 
            "image_embedding", 
            "image_data",
            "image_url" 
        })
        
        logger.info(f"Creating AssetDB instance with fields: {list(asset_dict.keys())}")
        
        # Create asset DB instance with image data and description embedding
        asset_db = AssetDB(
            **asset_dict,
            description_vector=description_embedding,
            image_embedding=image_embedding,  
            image_data=image_data,
            image_url=image_url 
        )
        
        # Convert to dict for MongoDB insertion
        asset_to_insert = asset_db.dict(by_alias=True)
        logger.info(f"Prepared asset for insertion with fields: {list(asset_to_insert.keys())}")
        
        # Insert into database
        result = await asset_collection.insert_one(asset_to_insert)
        logger.info(f"Asset inserted with ID: {result.inserted_id}")
        
        created_asset = await asset_collection.find_one({"_id": result.inserted_id})
        
        if not created_asset:
            logger.warning(f"Could not retrieve newly created asset with ID: {result.inserted_id}")
            return {
                "id": str(result.inserted_id),
                "status": "saved",
                "message": "Asset saved but not retrieved",
                "description_vector": description_embedding
            }
        serialized_asset = serialize_for_json(dict(created_asset))
        
        if "_id" in serialized_asset and "id" not in serialized_asset:
            serialized_asset["id"] = serialized_asset["_id"]
        
        if "image_data" in serialized_asset:
            serialized_asset["image_data_size"] = len(created_asset["image_data"])
            del serialized_asset["image_data"]
        
        logger.info(f"Asset saved successfully with ID: {serialized_asset.get('id')}")

        return {
            **serialized_asset,
            "status": "saved",
            "message": "Asset saved successfully with image data",
            "description_vector": description_embedding
        }
    
    except Exception as e:
        logger.error(f"Error in save_asset_with_image: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error saving asset with image: {str(e)}",
            "description_vector": description_embedding if description_embedding else []
        }


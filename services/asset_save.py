import logging
import numpy as np
from openai import OpenAI
import os
from typing import List, Dict, Any, Optional
from models.asset import AssetCreate, AssetDB
from database import asset_collection
from utils.db_helpers import serialize_for_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

async def get_embedding(text: str, api_key: Optional[str] = None) -> List[float]:
    """
    Generate embeddings for text using OpenAI's text-embedding-ada-002 model
    Updated for OpenAI Python SDK 1.0.0+
    """
    try:
        client = OpenAI(api_key=api_key or OPENAI_API_KEY)
        

        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        
        embedding = response.data[0].embedding
        return embedding
        
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return [0.0] * 1536  # Default size for ada-002 embeddings

def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors
    """
    if not vec1 or not vec2:
        return 0.0
        
    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)
    
    dot_product = np.dot(vec1_array, vec2_array)
    norm_vec1 = np.linalg.norm(vec1_array)
    norm_vec2 = np.linalg.norm(vec2_array)
    
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
        
    similarity = dot_product / (norm_vec1 * norm_vec2)
    return float(similarity)

async def find_similar_assets(asset: AssetCreate, embedding: List[float], threshold: float = 0.95) -> List[Dict[str, Any]]:
    """
    Find assets similar to the provided one based on embedding similarity
    Returns list of similar assets with similarity scores
    """
    all_assets = await asset_collection.find({"description_vector": {"$exists": True}}).to_list(1000)
    
    if not all_assets:
        return []
    
    similar_assets = []
    
    for db_asset in all_assets:
        if not db_asset.get("description_vector"):
            continue
            
        similarity = calculate_similarity(embedding, db_asset["description_vector"])
        
        if similarity > threshold:
            similar_assets.append({
                "id": str(db_asset["_id"]),
                "name": db_asset["name"],
                "type": db_asset["type"],
                "description": db_asset.get("description"),
                "image_url": db_asset.get("image_url"),
                "similarity": similarity
            })
    
    similar_assets.sort(key=lambda x: x["similarity"], reverse=True)
    return similar_assets

async def validate_asset(asset: AssetCreate, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate an asset by generating its embedding and finding similar assets
    Returns validation result with similar assets and embedding
    """
    text_to_embed = f"{asset.name} {asset.description or ''}"
    embedding = await get_embedding(text_to_embed, api_key)
    similar_assets = await find_similar_assets(asset, embedding)
    
    if similar_assets:
        return {
            "status": "similar_found",
            "message": f"Found {len(similar_assets)} similar assets",
            "similar_assets": similar_assets,
            "description_vector": embedding
        }
    else:
        return {
            "status": "ok",
            "message": "No similar assets found",
            "similar_assets": [],
            "description_vector": embedding
        }

async def save_asset_with_vector(asset: AssetCreate, embedding: Optional[List[float]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Save an asset with its embedding vector
    Generates embedding if not provided
    """
    try:
        # Generate embedding if not provided
        if embedding is None:
            text_to_embed = f"{asset.name} {asset.description or ''}"
            embedding = await get_embedding(text_to_embed, api_key)
        
        asset_dict = asset.model_dump(exclude={"description_vector"})
        asset_db = AssetDB(
            **asset_dict,
            description_vector=embedding
        )
        
        asset_to_insert = asset_db.dict(by_alias=True)
        
        result = await asset_collection.insert_one(asset_to_insert)
        created_asset = await asset_collection.find_one({"_id": result.inserted_id})
        
        if not created_asset:
            return {
                "id": str(result.inserted_id),
                "status": "saved",
                "message": "Asset saved but not retrieved",
                "description_vector": embedding
            }
        
        serialized_asset = serialize_for_json(dict(created_asset))
        if "_id" in serialized_asset and "id" not in serialized_asset:
            serialized_asset["id"] = serialized_asset["_id"]
        
        return {
            **serialized_asset,
            "status": "saved",
            "message": "Asset saved successfully",
            "description_vector": embedding
        }
    
    except Exception as e:
        logger.error(f"Error in save_asset_with_vector: {e}")
        return {
            "status": "error",
            "message": f"Error saving asset: {str(e)}",
            "description_vector": embedding if embedding else []
        }
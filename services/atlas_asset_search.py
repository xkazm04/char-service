from typing import List, Optional
from models.asset import AssetCreate, AssetResponse
from utils.openai_embeddings import get_embedding
from database import asset_collection
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AssetSearchQuery(BaseModel):
    query: str = Field(..., description="Natural language search query for assets")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")
    min_score: float = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score")
    asset_type: Optional[str] = Field(None, description="Filter by asset type")

class AssetSearchResult(BaseModel):
    asset: AssetResponse
    similarity_mongo: float = Field(..., description="MongoDB Atlas Vector Search similarity score (0-1)")
    
class AssetVectorSearchService:
    def __init__(self):
        self.collection = asset_collection
    
    async def create_vector_search_index(self):
        """Create Atlas Vector Search index for assets collection."""
        index_definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": "description_vector",
                    "numDimensions": 1536,  # OpenAI ada-002 dimensions
                    "similarity": "cosine"
                },
                {
                    "type": "filter",
                    "path": "type"
                },
                {
                    "type": "filter",
                    "path": "gen"
                },
                {
                    "type": "filter",
                    "path": "subcategory"
                }
            ]
        }
        
        try:
            logger.info("Asset vector search index definition created")
            return index_definition
        except Exception as e:
            logger.error(f"Failed to create asset vector search index: {e}")
            raise

    async def atlas_vector_search(self, search_query: AssetSearchQuery) -> List[AssetSearchResult]:
        """Perform semantic search using Atlas Vector Search with OpenAI embeddings."""
        try:
            # Generate embedding using existing OpenAI approach
            query_embedding = await get_embedding(search_query.query)
            
            # Build filter for Atlas Vector Search
            search_filter = {}
            if search_query.asset_type:
                search_filter["type"] = {"$eq": search_query.asset_type}
            
            # Atlas Vector Search aggregation pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "asset_vector_index",  # Name of your Atlas Search index
                        "path": "description_vector",
                        "queryVector": query_embedding,
                        "numCandidates": search_query.limit * 5,  # Oversampling for better results
                        "limit": search_query.limit,
                        "filter": search_filter if search_filter else {}
                    }
                },
                {
                    "$addFields": {
                        "similarity_mongo": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "similarity_mongo": {"$gte": search_query.min_score}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "type": 1,
                        "subcategory": 1,
                        "name": 1,
                        "gen": 1,
                        "description": 1,
                        "image_url": 1,
                        "image_data": 1,
                        "metadata": 1,
                        "created_at": 1,
                        "similarity_mongo": 1
                        # Exclude description_vector and image_embedding from results
                    }
                }
            ]
            
            # Execute search
            cursor = self.collection.aggregate(pipeline)
            results = []
            
            async for doc in cursor:
                # Convert MongoDB document to AssetResponse
                asset_data = dict(doc)
                similarity_score = asset_data.pop("similarity_mongo", 0.0)
                
                asset = AssetResponse(**asset_data)
                
                results.append(AssetSearchResult(
                    asset=asset,
                    similarity_mongo=similarity_score
                ))
            
            logger.info(f"Atlas vector search returned {len(results)} results for query: {search_query.query}")
            return results
            
        except Exception as e:
            logger.error(f"Atlas vector search failed: {e}")
            raise

    async def find_similar_assets_atlas(
        self, 
        asset: AssetCreate, 
        threshold: float = 0.95,
        limit: int = 10
    ) -> List[AssetSearchResult]:
        """Find similar assets using Atlas Vector Search instead of manual calculation."""
        try:
            # Generate embedding for the asset
            text_to_embed = f"{asset.name} {asset.description or ''}"
            asset_embedding = await get_embedding(text_to_embed)
            
            # Atlas Vector Search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "asset_vector_index",
                        "path": "description_vector",
                        "queryVector": asset_embedding,
                        "numCandidates": limit * 5,
                        "limit": limit
                    }
                },
                {
                    "$addFields": {
                        "similarity_mongo": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "similarity_mongo": {"$gte": threshold}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "type": 1,
                        "subcategory": 1,
                        "name": 1,
                        "gen": 1,
                        "description": 1,
                        "image_url": 1,
                        "metadata": 1,
                        "created_at": 1,
                        "similarity_mongo": 1
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            results = []
            
            async for doc in cursor:
                asset_data = dict(doc)
                similarity_score = asset_data.pop("similarity_mongo", 0.0)
                
                asset_response = AssetResponse(**asset_data)
                
                results.append(AssetSearchResult(
                    asset=asset_response,
                    similarity_mongo=similarity_score
                ))
            
            logger.info(f"Found {len(results)} similar assets using Atlas Vector Search")
            return results
            
        except Exception as e:
            logger.error(f"Failed to find similar assets with Atlas Vector Search: {e}")
            raise

    async def reindex_all_assets(self) -> int:
        """Add embeddings to all assets that don't have them."""
        count = 0
        try:
            # Find assets without embeddings
            cursor = self.collection.find({"description_vector": {"$exists": False}})
            
            async for doc in cursor:
                try:
                    # Generate embedding for existing asset
                    text_to_embed = f"{doc.get('name', '')} {doc.get('description', '')}"
                    embedding = await get_embedding(text_to_embed)
                    
                    # Update document with embedding
                    await self.collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "description_vector": embedding
                            }
                        }
                    )
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to reindex asset {doc['_id']}: {e}")
            
            logger.info(f"Reindexed {count} assets with embeddings")
            return count
            
        except Exception as e:
            logger.error(f"Failed to reindex assets: {e}")
            return count

# Global search service instance
asset_vector_search_service = AssetVectorSearchService()
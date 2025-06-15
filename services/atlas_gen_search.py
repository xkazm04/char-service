from typing import List
from models.generation import GenerationSearchQuery, GenerationSearchResult, Generation
from services.embedding import embedding_service
from database import generation_collection
import logging

logger = logging.getLogger(__name__)

class AtlasSearchService:
    def __init__(self):
        self.collection = generation_collection
    
    async def create_vector_search_index(self):
        """Create Atlas Vector Search index for generations collection."""
        index_definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 1536,  # OpenAI text-embedding-3-small dimensions
                    "similarity": "cosine"
                },
                {
                    "type": "filter",
                    "path": "meshy.status"  # Updated path for meshy status
                },
                {
                    "type": "filter", 
                    "path": "character_id"
                },
                {
                    "type": "filter",
                    "path": "created_at"
                }
            ]
        }
        
        try:
            logger.info("Vector search index definition created for OpenAI embeddings")
            return index_definition
        except Exception as e:
            logger.error(f"Failed to create vector search index: {e}")
            raise

    async def semantic_search(self, search_query: GenerationSearchQuery) -> List[GenerationSearchResult]:
        """Perform semantic search using Atlas Vector Search with OpenAI embeddings."""
        try:
            # Generate embedding for search query using OpenAI
            query_embedding = embedding_service.generate_embedding(search_query.query)
            
            if not query_embedding or all(x == 0.0 for x in query_embedding):
                logger.warning("Generated zero embedding for query, returning empty results")
                return []
            
            # Atlas Vector Search aggregation pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",  # Name of your Atlas Search index
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": search_query.limit * 10,  # Increased oversampling
                        "limit": search_query.limit,
                        "filter": {
                            # Only search generations that have completed processing
                            "$or": [
                                {"meshy.status": {"$eq": "succeeded"}},
                                {"meshy": {"$exists": False}},  # Include non-3D generations
                                {"has_3d_model": {"$eq": True}}
                            ]
                        }
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": search_query.min_score}
                    }
                },
                {
                    "$sort": {
                        "score": -1,  # Sort by relevance score
                        "created_at": -1  # Then by recency
                    }
                }
            ]
            
            # Execute search
            cursor = self.collection.aggregate(pipeline)
            results = []
            
            async for doc in cursor:
                try:
                    # Convert MongoDB document to Generation model
                    generation = Generation(**doc)
                    score = doc.get("score", 0.0)
                    
                    results.append(GenerationSearchResult(
                        generation=generation,
                        score=score
                    ))
                except Exception as e:
                    logger.warning(f"Failed to convert document to Generation model: {e}")
                    continue
            
            logger.info(f"Semantic search returned {len(results)} results for query: '{search_query.query}'")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []  # Return empty list instead of raising

    async def add_embedding_to_generation(self, generation_id: str) -> bool:
        """Add OpenAI embedding to existing generation."""
        try:
            # Get generation
            generation_doc = await self.collection.find_one({"_id": generation_id})
            if not generation_doc:
                logger.warning(f"Generation {generation_id} not found")
                return False
            
            # Generate searchable text and embedding
            searchable_text = embedding_service.create_searchable_text(generation_doc)
            embedding = embedding_service.generate_embedding(searchable_text)
            
            if not embedding or all(x == 0.0 for x in embedding):
                logger.warning(f"Failed to generate valid embedding for generation {generation_id}")
                return False
            
            # Update document
            result = await self.collection.update_one(
                {"_id": generation_id},
                {
                    "$set": {
                        "embedding": embedding,
                        "searchable_text": searchable_text
                    }
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Added embedding to generation {generation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add embedding to generation {generation_id}: {e}")
            return False

    async def reindex_all_generations(self, batch_size: int = 10) -> int:
        """Add embeddings to all generations that don't have them (in batches)."""
        count = 0
        try:
            # Find generations without embeddings
            cursor = self.collection.find(
                {"embedding": {"$exists": False}},
                {"_id": 1}  # Only fetch IDs for efficiency
            )
            
            generation_ids = []
            async for doc in cursor:
                generation_ids.append(str(doc["_id"]))
            
            logger.info(f"Found {len(generation_ids)} generations without embeddings")
            
            # Process in batches to avoid overwhelming the API
            for i in range(0, len(generation_ids), batch_size):
                batch_ids = generation_ids[i:i + batch_size]
                
                for gen_id in batch_ids:
                    success = await self.add_embedding_to_generation(gen_id)
                    if success:
                        count += 1
                
                logger.info(f"Processed batch {i//batch_size + 1}/{(len(generation_ids)-1)//batch_size + 1}")
            
            logger.info(f"Reindexed {count} generations with OpenAI embeddings")
            return count
            
        except Exception as e:
            logger.error(f"Failed to reindex generations: {e}")
            return count

# Global search service instance
atlas_search_service = AtlasSearchService()
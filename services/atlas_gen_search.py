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
                    "numDimensions": embedding_service.embedding_dim,
                    "similarity": "cosine"
                },
                {
                    "type": "filter",
                    "path": "status"
                },
                {
                    "type": "filter", 
                    "path": "character_type"
                },
                {
                    "type": "filter",
                    "path": "created_at"
                }
            ]
        }
        
        try:
            # Note: Index creation should be done via Atlas UI or Atlas CLI
            # This is for reference only
            logger.info("Vector search index definition created")
            return index_definition
        except Exception as e:
            logger.error(f"Failed to create vector search index: {e}")
            raise

    async def semantic_search(self, search_query: GenerationSearchQuery) -> List[GenerationSearchResult]:
        """Perform semantic search using Atlas Vector Search."""
        try:
            # Generate embedding for search query
            query_embedding = embedding_service.generate_embedding(search_query.query)
            
            # Atlas Vector Search aggregation pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",  # Name of your Atlas Search index
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": search_query.limit * 5,  # Oversampling for better results
                        "limit": search_query.limit,
                        "filter": {
                            "status": {"$eq": "completed"}  # Only search completed generations
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
                }
            ]
            
            # Execute search
            cursor = self.collection.aggregate(pipeline)
            results = []
            
            async for doc in cursor:
                # Convert MongoDB document to Generation model
                generation = Generation(**doc)
                score = doc.get("score", 0.0)
                
                results.append(GenerationSearchResult(
                    generation=generation,
                    score=score
                ))
            
            logger.info(f"Semantic search returned {len(results)} results for query: {search_query.query}")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise

    async def add_embedding_to_generation(self, generation_id: str) -> bool:
        """Add embedding to existing generation."""
        try:
            # Get generation
            generation_doc = await self.collection.find_one({"_id": generation_id})
            if not generation_doc:
                return False
            
            # Generate embedding
            searchable_text = embedding_service.create_searchable_text(generation_doc)
            embedding = embedding_service.generate_embedding(searchable_text)
            
            # Update document
            await self.collection.update_one(
                {"_id": generation_id},
                {
                    "$set": {
                        "embedding": embedding,
                        "searchable_text": searchable_text
                    }
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add embedding to generation {generation_id}: {e}")
            return False

    async def reindex_all_generations(self) -> int:
        """Add embeddings to all generations that don't have them."""
        count = 0
        try:
            # Find generations without embeddings
            cursor = self.collection.find({"embedding": {"$exists": False}})
            
            async for doc in cursor:
                success = await self.add_embedding_to_generation(doc["_id"])
                if success:
                    count += 1
            
            logger.info(f"Reindexed {count} generations with embeddings")
            return count
            
        except Exception as e:
            logger.error(f"Failed to reindex generations: {e}")
            return count

# Global search service instance
atlas_search_service = AtlasSearchService()
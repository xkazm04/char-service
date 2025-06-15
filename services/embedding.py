import logging
import os
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
# Load environment variables
load_dotenv()
# Ensure OpenAI API key is set


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        """Initialize the embedding service with OpenAI."""
        try:
            from config import config
            openai_api_key = config.openai_api_key
            self.client = OpenAI(api_key=openai_api_key)
            self.model_name = "text-embedding-3-small"  
            self.embedding_dim = 1536
            logger.info(f"Embedding service initialized with OpenAI model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text using OpenAI."""
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return [0.0] * self.embedding_dim
            
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text.strip()
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text: {text[:50]}...")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding for text '{text[:50]}...': {e}")
            # Return zero vector as fallback
            return [0.0] * self.embedding_dim

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch (more efficient)."""
        try:
            if not texts:
                return []
            
            # Filter out empty texts
            valid_texts = [text.strip() for text in texts if text and text.strip()]
            
            if not valid_texts:
                logger.warning("No valid texts provided for batch embedding")
                return [[0.0] * self.embedding_dim] * len(texts)
            
            # OpenAI supports batch embedding (up to 2048 inputs)
            response = self.client.embeddings.create(
                model=self.model_name,
                input=valid_texts
            )
            
            embeddings = [data.embedding for data in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.embedding_dim] * len(texts)

    def create_searchable_text(self, generation_data: dict) -> str:
        """Create searchable text from generation data."""
        searchable_parts = []
        
        # Add description
        if generation_data.get('description'):
            searchable_parts.append(generation_data['description'])
        
        # Add character type
        if generation_data.get('character_type'):
            searchable_parts.append(f"character type: {generation_data['character_type']}")
        
        # Add used assets information
        if generation_data.get('used_assets'):
            for asset in generation_data['used_assets']:
                if isinstance(asset, dict):
                    if asset.get('name'):
                        searchable_parts.append(f"asset: {asset['name']}")
                    if asset.get('description'):
                        searchable_parts.append(asset['description'])
                    if asset.get('type'):
                        searchable_parts.append(f"type: {asset['type']}")
                    if asset.get('subcategory'):
                        searchable_parts.append(f"category: {asset['subcategory']}")
        
        # Add Meshy metadata if available
        if generation_data.get('meshy') and isinstance(generation_data['meshy'], dict):
            meshy_data = generation_data['meshy']
            if meshy_data.get('texture_prompt'):
                searchable_parts.append(f"texture: {meshy_data['texture_prompt']}")
        
        # Add creation context
        if generation_data.get('leo_id'):
            searchable_parts.append("generated character asset")
        
        # Join all parts
        searchable_text = " ".join(filter(None, searchable_parts))
        
        # Ensure we have some content
        if not searchable_text.strip():
            searchable_text = "character generation"
        
        logger.debug(f"Created searchable text: {searchable_text[:100]}...")
        return searchable_text

    async def get_similarity_score(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            import numpy as np
            
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0

# Global embedding service instance
embedding_service = EmbeddingService()
import logging
import os
from sentence_transformers import SentenceTransformer
from typing import List
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding service with a sentence transformer model."""
        try:
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedding service initialized with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    def create_searchable_text(self, generation_data: dict) -> str:
        """Create searchable text from generation data."""
        searchable_parts = []
        
        # Add character type and description
        if generation_data.get('character_type'):
            searchable_parts.append(generation_data['character_type'])
        
        if generation_data.get('character_description'):
            searchable_parts.append(generation_data['character_description'])
        
        # Add tags if available
        if generation_data.get('tags'):
            searchable_parts.extend(generation_data['tags'])
        
        # Add any additional metadata
        if generation_data.get('style'):
            searchable_parts.append(f"style: {generation_data['style']}")
        
        if generation_data.get('mood'):
            searchable_parts.append(f"mood: {generation_data['mood']}")
        
        return " ".join(searchable_parts)

# Global embedding service instance
embedding_service = EmbeddingService()
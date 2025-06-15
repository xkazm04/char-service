import logging
import os
from typing import List, Optional
from dotenv import load_dotenv
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables early, but handle failures gracefully
try:
    load_dotenv()
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")

class EmbeddingService:
    def __init__(self):
        """Initialize the embedding service with OpenAI."""
        self.client = None
        self.model_name = "text-embedding-3-small"
        self.embedding_dim = 1536
        self._initialize_client()

    def _get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key using multiple fallback methods."""
        logger.info("🔍 Attempting to retrieve OpenAI API key...")
        
        # Method 1: Direct environment variable (most reliable)
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            logger.info("✅ Found OPENAI_API_KEY in os.environ")
            return api_key
        
        # Method 2: os.getenv (sometimes different from os.environ)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            logger.info("✅ Found OPENAI_API_KEY via os.getenv")
            return api_key
        
        # Method 3: Try config (delayed import to avoid circular dependencies)
        try:
            from config import config
            if hasattr(config, 'openai_api_key') and config.openai_api_key:
                logger.info("✅ Found OPENAI_API_KEY in config")
                return config.openai_api_key
        except ImportError as e:
            logger.warning(f"Could not import config: {e}")
        except Exception as e:
            logger.warning(f"Error accessing config.openai_api_key: {e}")
        
        # Method 4: Google Secret Manager (only if explicitly requested)
        if os.getenv("USE_SECRET_MANAGER", "false").lower() == "true":
            try:
                api_key = self._get_secret_from_manager("OPENAI_API_KEY")
                if api_key:
                    logger.info("✅ Found OPENAI_API_KEY in Secret Manager")
                    return api_key
            except Exception as e:
                logger.warning(f"Could not retrieve from Secret Manager: {e}")
        
        # Method 5: Debug all environment variables
        logger.error("❌ OPENAI_API_KEY not found. Debugging environment...")
        env_keys = [key for key in os.environ.keys() if 'OPENAI' in key.upper()]
        logger.error(f"Environment keys containing 'OPENAI': {env_keys}")
        
        # Check for common variations
        variations = [
            "OPENAI_API_KEY",
            "OPENAI_KEY", 
            "OPENAI_SECRET",
            "OPEN_AI_KEY",
            "OPEN_AI_API_KEY"
        ]
        
        for variation in variations:
            value = os.environ.get(variation) or os.getenv(variation)
            if value:
                logger.info(f"✅ Found API key in variation: {variation}")
                return value
        
        logger.error("❌ No OpenAI API key found in any location")
        return None

    def _get_secret_from_manager(self, secret_name: str) -> Optional[str]:
        """Get secret from Google Cloud Secret Manager"""
        try:
            from google.cloud import secretmanager
            
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "mage-c2b4a"
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            
            response = client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            if secret_value:
                logger.info(f"✅ Retrieved {secret_name} from Secret Manager")
                return secret_value
                
        except ImportError:
            logger.warning("Google Cloud Secret Manager library not available")
        except Exception as e:
            logger.warning(f"Could not retrieve secret {secret_name}: {e}")
        
        return None

    def _initialize_client(self):
        """Initialize OpenAI client with comprehensive error handling."""
        try:
            # Get API key using fallback methods
            api_key = self._get_openai_api_key()
            
            if not api_key:
                logger.error("💥 No OpenAI API key available. Cannot initialize embedding service.")
                raise ValueError("OpenAI API key is required but not found")
            
            # Validate API key format
            if not api_key.startswith(('sk-', 'sk-proj-')):
                logger.error(f"❌ Invalid OpenAI API key format. Key starts with: {api_key[:10]}...")
                raise ValueError("Invalid OpenAI API key format")
            
            # Import and initialize OpenAI client
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                logger.info(f"✅ Embedding service initialized with OpenAI model: {self.model_name}")
                
                # Test the connection with a small request
                self._test_connection()
                
            except ImportError as e:
                logger.error(f"OpenAI library not available: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                raise
                
        except Exception as e:
            logger.error(f"💥 Failed to initialize embedding service: {e}")
            raise

    def _test_connection(self):
        """Test OpenAI connection with a minimal request."""
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input="test"
            )
            if response.data:
                logger.info("✅ OpenAI connection test successful")
            else:
                logger.warning("⚠️ OpenAI connection test returned empty response")
        except Exception as e:
            logger.error(f"❌ OpenAI connection test failed: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text using OpenAI."""
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return [0.0] * self.embedding_dim
            
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
            return [0.0] * self.embedding_dim

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch (more efficient)."""
        try:
            if not self.client:
                logger.error("OpenAI client not initialized")
                return [[0.0] * self.embedding_dim] * len(texts)
            
            if not texts:
                return []
            
            valid_texts = [text.strip() for text in texts if text and text.strip()]
            
            if not valid_texts:
                logger.warning("No valid texts provided for batch embedding")
                return [[0.0] * self.embedding_dim] * len(texts)
            
            response = self.client.embeddings.create(
                model=self.model_name,
                input=valid_texts
            )
            
            embeddings = [data.embedding for data in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [[0.0] * self.embedding_dim] * len(texts)

    def create_searchable_text(self, generation_data: dict) -> str:
        """Create searchable text from generation data."""
        searchable_parts = []
        
        if generation_data.get('description'):
            searchable_parts.append(generation_data['description'])
        
        if generation_data.get('character_type'):
            searchable_parts.append(f"character type: {generation_data['character_type']}")
        
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
        
        if generation_data.get('meshy') and isinstance(generation_data['meshy'], dict):
            meshy_data = generation_data['meshy']
            if meshy_data.get('texture_prompt'):
                searchable_parts.append(f"texture: {meshy_data['texture_prompt']}")
        
        if generation_data.get('leo_id'):
            searchable_parts.append("generated character asset")
        
        searchable_text = " ".join(filter(None, searchable_parts))
        
        if not searchable_text.strip():
            searchable_text = "character generation"
        
        logger.debug(f"Created searchable text: {searchable_text[:100]}...")
        return searchable_text

    async def get_similarity_score(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            import numpy as np
            
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
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


# Lazy initialization to avoid import-time errors
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get embedding service instance (lazy initialization)."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

# For backward compatibility
embedding_service = None

def initialize_embedding_service():
    """Initialize the global embedding service."""
    global embedding_service
    try:
        embedding_service = get_embedding_service()
        logger.info("✅ Global embedding service initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize global embedding service: {e}")
        embedding_service = None

# Initialize on import (but catch errors gracefully)
try:
    initialize_embedding_service()
except Exception as e:
    logger.warning(f"Could not initialize embedding service on import: {e}")
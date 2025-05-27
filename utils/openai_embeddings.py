from openai import OpenAI
import os
from typing import List, Optional

import logging
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
        return [0.0] * 1536 
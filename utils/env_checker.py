import os
import logging

def force_check_openai_key():
    """Force check for OpenAI API key using multiple methods."""
    logger = logging.getLogger(__name__)
    
    # Method 1: Check all possible environment sources
    sources = [
        lambda: os.environ.get("OPENAI_API_KEY"),
        lambda: os.getenv("OPENAI_API_KEY"),
        lambda: os.environ.get("OPENAI_KEY"),
        lambda: os.getenv("OPENAI_KEY"),
    ]
    
    for i, source in enumerate(sources):
        try:
            key = source()
            if key:
                logger.info(f"✅ Found OpenAI key via method {i+1}")
                # Ensure it's set in both places
                os.environ["OPENAI_API_KEY"] = key
                return key
        except Exception as e:
            logger.warning(f"Method {i+1} failed: {e}")
    
    # Method 2: Check if Cloud Run metadata service has it
    if os.getenv('K_SERVICE'):  # We're on Cloud Run
        try:
            import requests
            metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/attributes/"
            headers = {"Metadata-Flavor": "Google"}
            
            # Try to get environment variables from metadata
            response = requests.get(metadata_url + "env", headers=headers, timeout=5)
            if response.status_code == 200:
                env_data = response.text
                for line in env_data.split('\n'):
                    if line.startswith('OPENAI_API_KEY='):
                        key = line.split('=', 1)[1]
                        os.environ["OPENAI_API_KEY"] = key
                        logger.info("✅ Found OpenAI key in Cloud Run metadata")
                        return key
        except Exception as e:
            logger.warning(f"Could not check Cloud Run metadata: {e}")
    
    logger.error("❌ No OpenAI API key found anywhere")
    return None
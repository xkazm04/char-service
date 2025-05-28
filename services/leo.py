import requests
import os
from dotenv import load_dotenv
import logging
from typing import Optional, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
logging.basicConfig(level=logging.DEBUG)

load_dotenv()

LEONARDO_API_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")

if not LEONARDO_API_KEY:
    raise ValueError("Leonardo API key is missing. Please set it in the .env file.")

HEADERS = {
    "Authorization": f"Bearer {LEONARDO_API_KEY}",
    "Content-Type": "application/json",
}

# Thread pool for background processing
executor = ThreadPoolExecutor(max_workers=3)

def delete_generation_api(generation_id: str):
    """Delete a generation by its ID."""
    url = f"{LEONARDO_API_BASE_URL}/generations/{generation_id}"
    try:
        response = requests.delete(url, headers=HEADERS)
        response.raise_for_status()
        logging.info("Generation deleted successfully.")
    except requests.exceptions.RequestException as e:
        logging.error("Error deleting generation: %s", e)
        raise

class userLoraId: 
    akUUID: int
    weight: int = 0.9
    preset: str = 'DYNAMIC'

def create_asset_img(
        gen: str, 
        element: Optional[userLoraId] = None,
        weight: Optional[float] = 0.9,
        preset: Optional[str] = 'DYNAMIC'
    ): 
    height = 720
    width = 1280
    
    if element:
        height = 1024
        width = 1024
        
    url = f"{LEONARDO_API_BASE_URL}/generations"
    instructions = f"""
        {gen}
    """
    payload = {
        "height": height,
        "width": width,
        'presetStyle': preset if preset else 'DYNAMIC',
        "userElements": [
            {
                "userLoraId": element,
                "weight": weight,
            }
        ] if element else [],
        "modelId": "b2614463-296c-462a-9586-aafdb8f00e36",
        "prompt": instructions,
        "num_images": 1,
    }
    try:
        logging.info("Calling Leonardo API with payload: %s", payload)
        response = requests.post(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error("Error calling Leonardo API: %s", e)
        raise
    
def get_generation(generation_id: str):
    """Retrieve generation based on generation_id."""
    url = f"{LEONARDO_API_BASE_URL}/generations/{generation_id}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        gen = data["generations_by_pk"]["generated_images"]
        return [
            {
                "url": image["url"],
                "id": image["id"],
                "nsfw": image["nsfw"],
                **({"motionMP4URL": image["motionMP4URL"]} if "motionMP4URL" in image else {})
            }
            for image in gen
        ]
    except requests.exceptions.RequestException as e:
        logging.error("Error fetching generated files: %s", e)
        raise

async def process_image_background(leonardo_url: str, asset_data: Dict[str, Any], generation_id: str):
    """
    Process image in background: download, save to DB, cleanup generation
    This runs asynchronously without blocking the response
    """
    try:
        # Import here to avoid circular imports
        from services.image_save import save_asset_with_image
        
        logging.info(f"Starting background processing for {leonardo_url}")
        
        # Run the blocking operations in executor
        loop = asyncio.get_running_loop()
        
        # Save asset with image (this downloads and processes the image)
        result = await loop.run_in_executor(
            executor, 
            lambda: save_asset_with_image(asset_data, leonardo_url)
        )
        
        # Cleanup generation after successful save
        await loop.run_in_executor(
            executor,
            delete_generation_api,
            generation_id
        )
        
        logging.info(f"Background processing completed for asset: {asset_data.get('name')}")
        return result
        
    except Exception as e:
        logging.error(f"Background processing failed: {e}")
        try:
            # Still try to cleanup the generation
            await loop.run_in_executor(executor, delete_generation_api, generation_id)
        except:
            pass

def create_asset_img_with_preview(
    gen: str,
    asset_data: Dict[str, Any],
    element: Optional[userLoraId] = None,
    weight: Optional[float] = 0.9,
    preset: Optional[str] = 'DYNAMIC'
) -> Dict[str, Any]:
    """
    Create asset image and return preview URL immediately while processing in background
    """
    try:
        # Step 1: Create generation
        creation_result = create_asset_img(gen, element, weight, preset)
        generation_id = creation_result.get("sdGenerationJob", {}).get("generationId")
        
        if not generation_id:
            raise Exception("No generation ID returned from Leonardo API")
        
        logging.info(f"Created new generation with ID: {generation_id}")
        
        # Step 2: Poll for completion and get preview URL
        import time
        max_attempts = 10
        delay = 3
        
        for attempt in range(max_attempts):
            try:
                images = get_generation(generation_id)
                if images and len(images) > 0:
                    leonardo_url = images[0]["url"]
                    logging.info(f"Images found after {attempt + 1} attempts.")
                    
                    # Step 3: Return preview URL immediately
                    preview_response = {
                        "status": "success",
                        "preview_url": leonardo_url,
                        "generation_id": generation_id,
                        "message": "Preview ready, processing in background"
                    }
                    
                    # Step 4: Start background processing (don't await)
                    # Create a new event loop for the background task
                    import threading
                    
                    def run_background_processing():
                        try:
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(
                                process_image_background(leonardo_url, asset_data, generation_id)
                            )
                            loop.close()
                        except Exception as e:
                            logging.error(f"Background thread failed: {e}")
                    
                    background_thread = threading.Thread(target=run_background_processing)
                    background_thread.daemon = True
                    background_thread.start()
                    
                    return preview_response
                    
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                
            if attempt < max_attempts - 1:
                time.sleep(delay)
        
        raise Exception(f"Failed to get images after {max_attempts} attempts")
        
    except Exception as e:
        logging.error(f"Error in create_asset_img_with_preview: {e}")
        raise
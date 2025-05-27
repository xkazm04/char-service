import requests
import os
from dotenv import load_dotenv
import logging
from typing import Optional
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
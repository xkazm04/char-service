import logging
from fastapi import APIRouter, HTTPException, Body
from services.leo import get_generation, delete_generation_api, create_asset_img
import asyncio
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(tags=["Leo"])


class DeleteGenerationsRequest(BaseModel):
    generation_ids: list[str]

@router.post("/delete")
async def delete_generations(request: DeleteGenerationsRequest):
    try:  
        for generation_id in request.generation_ids:
            delete_generation_api(generation_id)
            logging.info(f"Deleted generation with ID: {generation_id}")
        return {"status": "success", "message": "Generations deleted successfully."}
    except Exception as e:
        logging.error(f"Error in delete_generations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    
class GenerationRequest(BaseModel):
    gen: str  # asset.gen
    element: Optional[int] = Field(None, description="Element akUUID, e.g., 67297 for Jinx")
    generation_id: Optional[str] = Field(None, description="Optional generation ID for retries")
    
@router.post("/asset")
async def generate_and_poll_images(request: GenerationRequest):
    try:
        logging.info(f"Received generation request: {request}")
        if request.generation_id:
            try:
                logging.info(f"Deleting previous generation with ID: {request.generation_id}")
                delete_generation_api(request.generation_id)
            except Exception as e:
                logging.warning(f"Failed to delete previous generation {request.generation_id}: {e}")

        if request.element:
            create_response = create_asset_img(
                gen=request.gen,
                element=request.element,
            )
        else:
            create_response = create_asset_img(
                gen=request.gen,
            )
        generation_id = create_response["sdGenerationJob"]["generationId"]
        logging.info(f"Created new generation with ID: {generation_id}")

        # Poll for results
        for attempt in range(12):  # 12 attempts x 5s = 60s max
            try:
                images = get_generation(generation_id)
                if images:  
                    logging.info(f"Images found after {attempt + 1} attempts.")
                    return {"status": "success", "data": images, "gen": generation_id}
            except Exception as e:
                logging.warning(f"Polling attempt {attempt + 1} failed: {e}")

            await asyncio.sleep(5)  # Wait 5 seconds between polling attempts

        raise HTTPException(status_code=408, detail="Image generation timed out.")
    except Exception as e:
        logging.error(f"Error in generate_and_poll_images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
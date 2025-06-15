import asyncio
import logging
from datetime import datetime
from typing import Optional
import os
from database import generation_collection
from services.meshy import get_image_to_3d_task_status
from bson import ObjectId

logger = logging.getLogger(__name__)

class MeshyPollingService:
    def __init__(self):
        self.is_running = False
        self.polling_task: Optional[asyncio.Task] = None
        self.max_polling_attempts = 120  # 20 minutes with 10-second intervals
        self.polling_interval = 10  # seconds
        
    async def start_polling(self):
        """Start the background polling service"""
        if self.is_running:
            logger.warning("Polling service is already running")
            return
            
        self.is_running = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        logger.info("Meshy polling service started")
        
    async def stop_polling(self):
        """Stop the background polling service"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Meshy polling service stopped")
        
    async def _polling_loop(self):
        """Main polling loop"""
        while self.is_running:
            try:
                await self._poll_pending_generations()
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                logger.info("Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(self.polling_interval)
                
    async def _poll_pending_generations(self):
        """Poll all pending 3D generations"""
        try:
            # Find generations that are currently being polled or need to start polling
            pending_generations = await generation_collection.find({
                "$or": [
                    {"meshy.is_polling": True},
                    {
                        "meshy.meshy_id": {"$exists": True, "$ne": None},
                        "meshy.status": {"$in": ["processing", None]},
                        "meshy.is_polling": {"$ne": False}
                    }
                ]
            }).to_list(None)
            
            for generation in pending_generations:
                try:
                    await self._poll_single_generation(generation)
                except Exception as e:
                    logger.error(f"Error polling generation {generation['_id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error fetching pending generations: {e}")
            
    async def _poll_single_generation(self, generation):
        """Poll a single generation's 3D model status"""
        meshy_data = generation.get("meshy", {})
        task_id = meshy_data.get("meshy_id")
        
        if not task_id:
            return
            
        # Check if we've exceeded max attempts
        polling_attempts = meshy_data.get("polling_attempts", 0)
        if polling_attempts >= self.max_polling_attempts:
            logger.warning(f"Max polling attempts reached for generation {generation['_id']}")
            await self._mark_generation_failed(generation["_id"], "Max polling attempts exceeded")
            return
            
        try:
            from config import config
            api_key = config.meshy_api_key
            if not api_key:
                logger.error("MESHY_API_KEY not found in environment variables")
                return
                
            # Poll Meshy API
            response = get_image_to_3d_task_status(task_id, api_key)
            
            # Map status
            status_mapping = {
                "SUCCEEDED": "completed",
                "FAILED": "failed",
                "PENDING": "processing",
                "PROCESSING": "processing"
            }
            
            mapped_status = status_mapping.get(response.get("status", ""), "processing")
            
            # Update polling info
            update_data = {
                "meshy.last_polled": datetime.now(),
                "meshy.polling_attempts": polling_attempts + 1,
                "meshy.progress": response.get("progress", 0),
                "meshy.status": mapped_status
            }
            
            if mapped_status == "completed":
                # Update with completed data
                update_data.update({
                    "meshy.glb_url": response.get("model_urls", {}).get("glb"),
                    "meshy.fbx_url": response.get("model_urls", {}).get("fbx"),
                    "meshy.usdz_url": response.get("model_urls", {}).get("usdz"),
                    "meshy.obj_url": response.get("model_urls", {}).get("obj"),
                    "meshy.thumbnail_url": response.get("thumbnail_url"),
                    "meshy.texture_prompt": response.get("texture_prompt", ""),
                    "meshy.texture_urls": response.get("texture_urls", []),
                    "meshy.is_polling": False,
                    "is_3d_generating": False,
                    "has_3d_model": True
                })
                logger.info(f"3D model completed for generation {generation['_id']}")
                
            elif mapped_status == "failed":
                # Update with error data
                update_data.update({
                    "meshy.task_error": response.get("task_error", {"error": "Task failed"}),
                    "meshy.is_polling": False,
                    "is_3d_generating": False,
                    "has_3d_model": False
                })
                logger.error(f"3D model generation failed for generation {generation['_id']}")
                
            else:
                # Still processing, continue polling
                update_data["meshy.is_polling"] = True
                
            # Update the database
            await generation_collection.update_one(
                {"_id": generation["_id"]},
                {"$set": update_data}
            )
            
        except Exception as e:
            logger.error(f"Error polling Meshy API for generation {generation['_id']}: {e}")
            # Don't mark as failed immediately, let it retry
            await generation_collection.update_one(
                {"_id": generation["_id"]},
                {"$set": {
                    "meshy.last_polled": datetime.now(),
                    "meshy.polling_attempts": polling_attempts + 1
                }}
            )
            
    async def _mark_generation_failed(self, generation_id: ObjectId, error_message: str):
        """Mark a generation as failed"""
        await generation_collection.update_one(
            {"_id": generation_id},
            {"$set": {
                "meshy.status": "failed",
                "meshy.is_polling": False,
                "meshy.task_error": {"error": error_message},
                "is_3d_generating": False,
                "has_3d_model": False
            }}
        )

# Global instance
meshy_polling_service = MeshyPollingService()
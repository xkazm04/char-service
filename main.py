from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes import api_router 
from services.background_polling import meshy_polling_service
import os
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await meshy_polling_service.start_polling()
    yield
    await meshy_polling_service.stop_polling()

app = FastAPI(lifespan=lifespan, title="Character Creator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000, https://pikselplay.netlify.app", "https://char-ui.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="", tags=["Char"])

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment"""
    try:
        return {"status": "healthy", "timestamp": "2025-05-27"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

def refresh_environment():
    """Force refresh environment variables on Cloud Run."""
    try:
        # Check if we're on Cloud Run
        if os.getenv('K_SERVICE'):
            logger.info("🏃 Running on Google Cloud Run")
            
            # Force reload environment variables
            import subprocess
            result = subprocess.run(['env'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '=' in line and 'OPENAI_API_KEY' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
                        logger.info(f"✅ Refreshed {key} from environment")
            
    except Exception as e:
        logger.warning(f"Could not refresh environment: {e}")

# Call this before any imports that use environment variables
refresh_environment()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
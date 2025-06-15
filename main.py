from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes import api_router 
from services.background_polling import meshy_polling_service
import os
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    await meshy_polling_service.start_polling()
    yield
    await meshy_polling_service.stop_polling()

app = FastAPI(lifespan=lifespan, title="Character Creator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000, pikselplay.netlify.app"],
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

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = [
        'MONGO_URI',
        'DB_NAME',
        'OPENAI_API_KEY',
        'GOOGLE_API_KEY'
    ]
    
    optional_vars = [
        'LEONARDO_API_KEY',
        'GROQ_API_KEY',
        'MESHY_API_KEY',
        'HF_API_KEY'
    ]
    
    missing_required = []
    missing_optional = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
    
    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)
    
    if missing_required:
        logging.error(f"Missing required environment variables: {missing_required}")
        raise ValueError(f"Missing required environment variables: {missing_required}")
    
    if missing_optional:
        logging.warning(f"Missing optional environment variables: {missing_optional}")
    
    logging.info("Environment validation completed successfully")

validate_environment()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
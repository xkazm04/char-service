from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes import api_router 
from services.background_polling import meshy_polling_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    await meshy_polling_service.start_polling()
    yield
    await meshy_polling_service.stop_polling()

app = FastAPI(lifespan=lifespan, title="Character Creator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
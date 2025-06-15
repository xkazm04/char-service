from fastapi import APIRouter, HTTPException, Form
from services.image_analyze import analyze_image, analyze_with_gemini
from fastapi import UploadFile, File
from typing import Optional
from pydantic import BaseModel, Field
import logging
import asyncio
import json

router = APIRouter()
logging.basicConfig(level=logging.INFO)

class ModelConfig(BaseModel):
    enabled: bool = False  # Default to False
    apiKey: Optional[str] = None

class AnalysisConfig(BaseModel):
    openai: Optional[ModelConfig] = Field(default_factory=lambda: ModelConfig(enabled=False))
    gemini: Optional[ModelConfig] = Field(default_factory=lambda: ModelConfig(enabled=False))
    groq: Optional[ModelConfig] = Field(default_factory=lambda: ModelConfig(enabled=False))
    
    def model_post_init(self, __context):
        """Ensure all fields have default values if not provided"""
        if self.openai is None:
            self.openai = ModelConfig(enabled=False)
        if self.gemini is None:
            self.gemini = ModelConfig(enabled=False)
        if self.groq is None:
            self.groq = ModelConfig(enabled=False)

@router.post("/")
async def analyze_asset_image(
    file: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Analyze an uploaded image using selected models based on configuration.
    Config parameter specifies which models to use and provides API keys if needed.
    """
    contents = await file.read()
    logging.info(f"Received file: {file.filename} of size {len(contents)} bytes")
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)
    
    logging.info(f"Saved file to temporary path: {temp_path}")
    logging.info(f"Received config: {config}")  # Debug log

    try:
        config_dict = json.loads(config)
        logging.info(f"Parsed config dict: {config_dict}")  # Debug log
        
        # Ensure all required fields exist with defaults
        normalized_config = {
            "openai": config_dict.get("openai", {"enabled": False}),
            "gemini": config_dict.get("gemini", {"enabled": False}),
            "groq": config_dict.get("groq", {"enabled": False})
        }
        
        logging.info(f"Normalized config: {normalized_config}")  # Debug log
        analysis_config = AnalysisConfig(**normalized_config)
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    except Exception as e:
        logging.error(f"Error parsing configuration: {e}")
        logging.error(f"Config dict type: {type(config_dict)}")
        logging.error(f"Config dict content: {config_dict}")
        raise HTTPException(status_code=400, detail=f"Invalid configuration format: {str(e)}")
    
    # Check if at least one model is enabled
    if not any([analysis_config.openai.enabled, analysis_config.gemini.enabled, analysis_config.groq.enabled]):
        raise HTTPException(status_code=400, detail="At least one model must be enabled")
    
    tasks = []
    async def run_blocking(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    results = {
        "groq": [],
        "openai": [],
        "gemini": []
    }
    
    # Only run analysis for enabled models
    if analysis_config.groq and analysis_config.groq.enabled:
        api_key = analysis_config.groq.apiKey if analysis_config.groq.apiKey else None
        tasks.append(("groq", run_blocking(analyze_image, temp_path, "groq", api_key)))
    
    if analysis_config.openai and analysis_config.openai.enabled:
        api_key = analysis_config.openai.apiKey if analysis_config.openai.apiKey else None
        tasks.append(("openai", run_blocking(analyze_image, temp_path, "openai", api_key)))
    
    if analysis_config.gemini and analysis_config.gemini.enabled:
        api_key = analysis_config.gemini.apiKey if analysis_config.gemini.apiKey else None
        tasks.append(("gemini", run_blocking(analyze_with_gemini, temp_path, api_key)))
    
    try:
        for model_name, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=120)
                if isinstance(result, list):
                    results[model_name] = result
                elif isinstance(result, dict) and not result:
                    results[model_name] = []
                elif isinstance(result, dict):
                    if any(isinstance(v, list) for v in result.values()):
                        for v in result.values():
                            if isinstance(v, list):
                                results[model_name] = v
                                break
                    else:
                        results[model_name] = [result]
                else:
                    results[model_name] = []
                    logging.warning(f"Unexpected result type from {model_name}: {type(result)}")
            except Exception as e:
                logging.error(f"{model_name.capitalize()} analysis failed: {e}")
                results[model_name] = []
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Image analysis timed out")
    except Exception as e:
        logging.error(f"Unexpected error during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error during image analysis: {str(e)}")

    return results
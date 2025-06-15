import os
import logging

class Config:
    def __init__(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  
        except Exception:
            pass  
        
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.is_production = self.environment == "production"
        
        # Database
        self.mongo_uri = os.getenv("MONGO_URI")
        self.db_name = os.getenv("DB_NAME", "char")
        
        # Required APIs
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        
        # Optional APIs
        self.leonardo_api_key = os.getenv("LEONARDO_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.meshy_api_key = os.getenv("MESHY_API_KEY")
        

config = Config()
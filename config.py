import os
import logging

class Config:
    def __init__(self):
        # Try to load .env for local development
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # dotenv not available
        except Exception:
            pass  # .env file doesn't exist
        
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
        
        self.validate()
    
    def validate(self):
        """Validate configuration"""
        required = {
            'MONGO_URI': self.mongo_uri,
            'OPENAI_API_KEY': self.openai_api_key,
            'GOOGLE_API_KEY': self.google_api_key
        }
        
        missing = [key for key, value in required.items() if not value]
        
        if missing:
            logging.error(f"Missing required environment variables: {missing}")
            raise ValueError(f"Missing required environment variables: {missing}")
        
        optional_missing = []
        if not self.leonardo_api_key:
            optional_missing.append('LEONARDO_API_KEY')
        
        if optional_missing:
            logging.warning(f"Missing optional environment variables: {optional_missing}")

# Global config instance
config = Config()
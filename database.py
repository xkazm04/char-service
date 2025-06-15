import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import logging
from config import config
logger = logging.getLogger(__name__)

load_dotenv()

MONGO_URI = config.mongo_uri
DB_NAME = config.db_name

client = AsyncIOMotorClient(MONGO_URI)
database = client[DB_NAME]

character_collection = database.get_collection("characters")
asset_collection = database.get_collection("assets")
generation_collection = database.get_collection("generations")


cache_collection = database["asset_cache"]

async def connect_to_mongo():
    try:
        await client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise e

async def setup_cache_indexes():
    """Set up indexes for the cache collection"""
    try:
        # TTL index for automatic expiration
        await cache_collection.create_index(
            "expires_at", 
            expireAfterSeconds=0
        )
        
        # Index on cache_key for fast lookups
        await cache_collection.create_index("cache_key", unique=True)
        
        logging.info("Cache indexes created successfully")
    except Exception as e:
        logging.error(f"Error creating cache indexes: {e}")

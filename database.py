import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "character_creator")

# Create async client
client = AsyncIOMotorClient(MONGO_URI)
database = client[DB_NAME]

# Collections
character_collection = database.get_collection("characters")
asset_collection = database.get_collection("assets")

# Connection validation function
async def connect_to_mongo():
    try:
        # Send a ping to confirm a successful connection
        await client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise e
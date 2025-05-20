import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "character_creator")

client = AsyncIOMotorClient(MONGO_URI)
database = client[DB_NAME]

character_collection = database.get_collection("characters")
asset_collection = database.get_collection("assets")
generation_collection = database.get_collection("generations")

async def connect_to_mongo():
    try:
        await client.admin.command('ping')
        print("Connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise e
from bson import ObjectId
from datetime import datetime

def serialize_for_json(obj: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    result = {}
    for key, value in obj.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, bytes):
            result[key] = f"<binary data of size {len(value)} bytes>"
        elif isinstance(value, list) and len(value) > 100:
            result[key] = f"<array of {len(value)} items>"
        elif isinstance(value, dict):
            result[key] = serialize_for_json(value)
        else:
            result[key] = value
    return result

async def safe_find_one(collection, query):
    """
    Safely find a document and serialize it for JSON
    """
    result = await collection.find_one(query)
    if result:
        serialized = serialize_for_json(dict(result))
        if "_id" in serialized and "id" not in serialized:
            serialized["id"] = serialized["_id"]
        return serialized
    return None

async def safe_find_many(collection, query, limit=1000):
    """
    Safely find multiple documents and serialize them for JSON
    """
    results = await collection.find(query).to_list(limit)
    serialized_results = []
    
    for result in results:
        serialized = serialize_for_json(dict(result))
        if "_id" in serialized and "id" not in serialized:
            serialized["id"] = serialized["_id"]
        serialized_results.append(serialized)
    
    return serialized_results
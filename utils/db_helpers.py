from bson import ObjectId
from datetime import datetime

def serialize_for_json(obj):
    """
    Convert non-serializable types to serializable types
    - ObjectId to string
    - datetime to ISO format string
    """
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

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
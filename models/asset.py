from typing import List, Optional, Any, Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from datetime import datetime
from bson import ObjectId

# Helper for ObjectId conversion
def validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError("Invalid ObjectId")

# Define a type for ObjectId fields
PyObjectId = Annotated[ObjectId, BeforeValidator(validate_object_id)]


class AssetBase(BaseModel):
    name: str
    type: str  # e.g., weapon, armor, accessory
    slot: str  # e.g., head, chest, weapon
    rarity: str = "common"  # common, uncommon, rare, etc.
    stats: dict = {}
    image_url: Optional[str] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class AssetDB(AssetBase):
    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60d21b4967d0d8992e610c87",
                "name": "Excalibur",
                "type": "weapon",
                "slot": "main_hand",
                "rarity": "legendary",
                "stats": {"damage": 50, "critical_chance": 15},
                "image_url": "https://example.com/excalibur.png",
                "created_at": "2023-05-14T00:00:00",
                "updated_at": "2023-05-14T00:00:00"
            }
        }
    )


class Hairstyle(AssetBase):
    description: str
    description_vector: List[float]    # Enables semantic matching
    image_embedding: List[float]       # Used for image-to-image similarity
    metadata: dict = {}
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Long Wavy Hair",
                "type": "hairstyle",
                "slot": "hair",
                "rarity": "common",
                "stats": {},
                "image_url": "/images/assets/hair01.png",
                "description": "A long flowing hairstyle with waves.",
                "description_vector": [0.34, 0.21],
                "image_embedding": [0.67, 0.13],
                "metadata": {
                    "tags": ["feminine", "elegant", "long"],
                    "compatible_with": ["female", "elf"]
                }
            }
        }
    )
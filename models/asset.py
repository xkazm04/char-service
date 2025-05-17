from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema

class PydanticObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, 
        _source_type: Any, 
        _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ]),
        ])

    @classmethod
    def validate(cls, v: str) -> ObjectId:
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


class AssetMetadata(BaseModel):
    tags: Optional[List[str]] = None
    compatible_with: Optional[List[str]] = None


class AssetBase(BaseModel):
    type: str  
    subcategory: Optional[str] = None
    name: str
    gen: str 
    description: Optional[str] = None
    description_vector: Optional[List[float]] = None
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None 
    image_embedding: Optional[List[float]] = None
    metadata: Optional[AssetMetadata] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class AssetDB(AssetBase):
    id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )


class AssetCreate(AssetBase):
    pass


class AssetResponse(AssetBase):
    _id: str
    created_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60d21b4967d0d8992e610c87",
                "type": "hairstyle",
                "name": "Long Wavy Hair",
                "gen": "fantasy",
                "description": "A long flowing hairstyle with waves.",
                "description_vector": [0.34, 0.21, 0.56],
                "image_url": "/images/assets/hair01.png",
                "image_embedding": [0.67, 0.13, 0.89],
                "metadata": {
                    "tags": ["feminine", "elegant", "long"],
                    "compatible_with": ["female", "elf"]
                },
                "created_at": "2023-05-14T00:00:00"
            }
        }
    )
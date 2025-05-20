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
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat(timespec='seconds')}
    )


class AssetDB(AssetBase):
    # id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id") # Using _id directly from mongo
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat(timespec='seconds')},
        populate_by_name=True # Allows using alias, e.g. if we had id = Field(alias="_id")
    )


class AssetCreate(AssetBase):
    # For creation, we might not expect base64 data directly, image_data (bytes) would be used
    pass


class AssetResponse(AssetBase):
    id: PydanticObjectId = Field(alias="_id") # Changed type from str to PydanticObjectId
    created_at: datetime

    # Add fields for Base64 image representation
    image_data_base64: Optional[str] = None
    image_content_type: Optional[str] = None

    # Explicitly exclude the raw bytes data from the response model
    image_data: Optional[bytes] = Field(None, exclude=True)
    
    model_config = ConfigDict(
        from_attributes=True, # Renamed from orm_mode in Pydantic v2
        populate_by_name=True, # Allows mapping _id to id
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat(timespec='seconds')+"Z"}, # Ensure ISO format with Z
        json_schema_extra={
            "example": {
                "id": "60d21b4967d0d8992e610c87", # Example output remains a string
                "type": "hairstyle",
                "subcategory": "wavy",
                "name": "Long Wavy Hair",
                "gen": "fantasy",
                "description": "A long flowing hairstyle with waves.",
                "image_url": "/images/assets/hair01.png",
                "image_data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAUA...",
                "image_content_type": "image/png",
                "metadata": {
                    "tags": ["feminine", "elegant", "long"],
                    "compatible_with": ["female", "elf"]
                },
                "created_at": "2023-05-14T00:00:00Z",
                # description_vector and image_embedding are omitted as they are optional
                # and likely large for a list response.
            }
        }
    )

class PaginatedAssetResponse(BaseModel):
    assets: List[AssetResponse]
    total_assets: int
    total_pages: int
    current_page: int
    page_size: int
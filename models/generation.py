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


class MeshyMetadata(BaseModel):
    meshy_id: str
    glb_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    texture_prompt: Optional[str] = None
    texture_urls: Optional[List[dict[str, str]]] = None
    task_error: Optional[dict[str, Any]] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
class UsedAssets(BaseModel):
    id: str
    name: str
    type: str
    category: str
    description: str
    image_data: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class GenerationBase(BaseModel):
    character_id: PydanticObjectId
    image_url: Optional[str] = None
    description: Optional[str] = None
    used_assets: Optional[List[UsedAssets]] = None
    description_vector: Optional[List[float]] = None
    meshy: Optional[MeshyMetadata] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class GenerationResponse(GenerationBase):
    id: PydanticObjectId = Field(default_factory=PydanticObjectId, alias="_id")

    class Config:
        json_encoders = {
            ObjectId: str
        }
        schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "character_id": "507f1f77bcf86cd799439012",
                "image_url": "https://example.com/image.png",
                "description": "A character description",
                "meshy": {
                    "meshy_id": "mesh_123",
                    "glb_url": "https://example.com/model.glb",
                    "thumbnail_url": "https://example.com/thumbnail.png",
                    "texture_prompt": "A texture prompt",
                    "texture_urls": [{"url": "https://example.com/texture.png"}],
                    "task_error": {"error_code": 404, "error_message": "Not Found"}
                },
                "created_at": datetime.utcnow()
            }
        }
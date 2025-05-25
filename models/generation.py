from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema

class PydanticObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

class MeshyMetadata(BaseModel):
    meshy_id: str
    glb_url: Optional[str] = None
    fbx_url: Optional[str] = None  # Added
    usdz_url: Optional[str] = None  # Added
    obj_url: Optional[str] = None  # Added
    thumbnail_url: Optional[str] = None
    texture_prompt: Optional[str] = None
    texture_urls: Optional[List[dict[str, str]]] = None
    task_error: Optional[dict[str, Any]] = None
    progress: Optional[int] = None  # Added
    status: Optional[str] = None  # Added

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
    leo_id: Optional[str] = None  # Leo generation ID
    image_url: Optional[str] = None # Leonardo url
    description: Optional[str] = None
    used_assets: Optional[List[UsedAssets]] = None
    description_vector: Optional[List[float]] = None
    meshy: Optional[MeshyMetadata] = None  # Added meshy metadata

class GenerationResponse(GenerationBase):
    id: PydanticObjectId = Field(alias="_id")
    created_at: datetime

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )
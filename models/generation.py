from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema
from services.embedding import embedding_service

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
    fbx_url: Optional[str] = None
    usdz_url: Optional[str] = None
    obj_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    texture_prompt: Optional[str] = None
    texture_urls: Optional[List[dict[str, str]]] = None
    task_error: Optional[dict[str, Any]] = None
    progress: Optional[int] = None
    status: Optional[str] = None
    is_polling: Optional[bool] = False
    last_polled: Optional[datetime] = None
    polling_attempts: Optional[int] = 0

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
class UsedAssets(BaseModel):
    id: str
    name: str
    type: str
    subcategory: str
    description: str
    image_data: str
    _id: Optional[str] = None
    url: Optional[str] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    def __init__(self, **data):
        if 'id' in data and '_id' not in data:
            data['_id'] = data['id']
        elif '_id' in data and 'id' not in data:
            data['id'] = data['_id']
        super().__init__(**data)

class GenerationBase(BaseModel):
    character_id: PydanticObjectId
    leo_id: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    used_assets: Optional[List[UsedAssets]] = None
    description_vector: Optional[List[float]] = None
    meshy: Optional[MeshyMetadata] = None
    created_at: datetime = Field(default_factory=datetime.now)
    # Add 3D generation status tracking
    is_3d_generating: Optional[bool] = False
    has_3d_model: Optional[bool] = False

class GenerationResponse(GenerationBase):
    id: PydanticObjectId = Field(alias="_id")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )

class Generation(GenerationResponse):
    # Add vector embedding field
    embedding: Optional[List[float]] = Field(None, description="Vector embedding for semantic search")
    searchable_text: Optional[str] = Field(None, description="Preprocessed text for embedding generation")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class GenerationCreate(Generation):
    def generate_embedding_data(self) -> tuple[str, List[float]]:
        """Generate searchable text and embedding for this generation."""
        generation_dict = self.dict()
        searchable_text = embedding_service.create_searchable_text(generation_dict)
        embedding = embedding_service.generate_embedding(searchable_text)
        
        return searchable_text, embedding

class GenerationSearchQuery(BaseModel):
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")
    min_score: float = Field(0.5, ge=0.0, le=1.0, description="Minimum similarity score")

class GenerationSearchResult(BaseModel):
    generation: Generation
    score: float = Field(..., description="Similarity score (0-1)")
from typing import List, Optional, Any, Dict, ClassVar, Annotated
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator, GetCoreSchemaHandler
from datetime import datetime
from bson import ObjectId
from pydantic_core import core_schema

# Better ObjectId handling for Pydantic v2
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


class CharacterAttributes(BaseModel):
    gender: Optional[str] = None
    class_type: Optional[str] = None
    hairstyle_id: Optional[PydanticObjectId] = None
    equipment_ids: Optional[List[PydanticObjectId]] = None
    accessories_ids: Optional[List[PydanticObjectId]] = None


class CharacterBase(BaseModel):
    name: str
    type: Optional[str] = None
    description: Optional[str] = None
    faction_id: Optional[PydanticObjectId] = None
    description_vector: Optional[List[float]] = None
    
    # Avatar images and embeddings
    avatar_url: Optional[str] = None
    avatar_embedding: Optional[List[float]] = None
    body_url: Optional[str] = None
    body_embedding: Optional[List[float]] = None
    transparent_url: Optional[str] = None
    transparent_embedding: Optional[List[float]] = None
    
    # Attributes
    attributes: Optional[CharacterAttributes] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class CharacterDB(CharacterBase):
    id: PydanticObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    creator_user_id: Optional[PydanticObjectId] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )


class CharacterCreate(CharacterBase):
    creator_user_id: Optional[PydanticObjectId] = None


class CharacterResponse(CharacterBase):
    id: str
    created_at: datetime
    creator_user_id: Optional[str] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60d21b4967d0d8992e610c85",
                "name": "Elara",
                "type": "Playable",
                "description": "A skilled female archer with long hair, wearing a green cape.",
                "faction_id": "60d21b4967d0d8992e610c86",
                "description_vector": [0.12, 0.43, 0.67],
                "avatar_url": "/images/char/elara.png",
                "avatar_embedding": [0.09, 0.45, 0.23],
                "body_url": "/images/char/elara_full.png",
                "body_embedding": [0.19, 0.35, 0.53],
                "transparent_url": "/images/char/elara_transparent.png",
                "transparent_embedding": [0.29, 0.15, 0.73],
                "attributes": {
                    "gender": "female",
                    "class_type": "archer",
                    "hairstyle_id": "60d21b4967d0d8992e610c87",
                    "equipment_ids": ["60d21b4967d0d8992e610c88", "60d21b4967d0d8992e610c89"],
                    "accessories_ids": ["60d21b4967d0d8992e610c90"]
                },
                "created_at": "2023-05-14T00:00:00",
                "creator_user_id": "60d21b4967d0d8992e610c91"
            }
        }
    )
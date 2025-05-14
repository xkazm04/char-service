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


class CharacterBase(BaseModel):
    name: str
    class_type: str
    level: int = 1
    attributes: dict = {}
    equipped_assets: List[PyObjectId] = []
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class CharacterDB(CharacterBase):
    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        populate_by_name=True
    )


class CharacterCreate(CharacterBase):
    pass


class CharacterResponse(CharacterBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "60d21b4967d0d8992e610c85",
                "name": "Warrior",
                "class_type": "Fighter",
                "level": 5,
                "attributes": {"strength": 10, "dexterity": 8, "intelligence": 5},
                "equipped_assets": ["60d21b4967d0d8992e610c87"],
                "created_at": "2023-05-14T00:00:00",
                "updated_at": "2023-05-14T00:00:00"
            }
        }
    )
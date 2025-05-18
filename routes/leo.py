from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List

from models.character import CharacterCreate, CharacterResponse, CharacterDB
from database import character_collection

router = APIRouter()

@router.get("/", response_model=List[CharacterResponse])
async def get_characters():
    """
    Get all characters from the database
    """
    characters = await character_collection.find().to_list(1000)
    return characters

@router.get("/{id}", response_model=CharacterResponse)
async def get_character(id: str):
    """
    Get a specific character by ID
    """
    if (character := await character_collection.find_one({"_id": id})) is not None:
        return character
    
    raise HTTPException(status_code=404, detail=f"Character with id {id} not found")

@router.post("/", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(character: CharacterCreate = Body(...)):
    """
    Create a new character
    """
    character = jsonable_encoder(CharacterDB(**character.dict()))
    new_character = await character_collection.insert_one(character)
    created_character = await character_collection.find_one({"_id": new_character.inserted_id})
    
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=created_character)
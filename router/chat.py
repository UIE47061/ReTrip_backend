# router/chat.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from functions.geminiChatFunction import search_with_gemini_candidates
from functions.geminiChatFunction import chat_travel_question, generate_attraction_tags

router = APIRouter(prefix="/chat", tags=["AI API"])

class SearchRequest(BaseModel):
    message: str

class AttractionInfo(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    town: Optional[str] = None
    main_image_url: Optional[str] = None

class IdsResponse(BaseModel):
    ids: List[str]
    # optionally include found records for debugging; can be removed later
    # found: Optional[List[AttractionInfo]] = None

@router.post("/search", response_model=IdsResponse, summary="根據描述搜尋景點")
async def search_attractions(request: SearchRequest):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="請提供景點描述")
        
    response_data = await search_with_gemini_candidates(request.message)
    
    if "error" in response_data:
        raise HTTPException(status_code=500, detail=response_data["error"])
    
    return response_data


class AskRequest(BaseModel):
    message: str

class AskResponse(BaseModel):
    answer: str


@router.post("/ask", response_model=AskResponse, summary="旅遊問答 chat API (純回答)")
async def ask_travel_question(request: AskRequest):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="請提供問題內容")
    resp = await chat_travel_question(request.message)
    if "error" in resp:
        raise HTTPException(status_code=500, detail=resp["error"])
    return {"answer": resp.get("answer", "")}


class TagRequest(BaseModel):
    name: str

class TagResponse(BaseModel):
    tags: List[str]


@router.post("/tags", response_model=TagResponse, summary="為景點產生 3 個 tag")
async def generate_tags(request: TagRequest):
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="請提供景點名稱")
    resp = await generate_attraction_tags(request.name)
    if "error" in resp:
        raise HTTPException(status_code=500, detail=resp["error"])
    return {"tags": resp.get("tags", [])}

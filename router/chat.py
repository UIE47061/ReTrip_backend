# router/chat.py (“AI 結構化生成”版本)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

# 導入我們在 geminiChatFunction.py 中定義的核心邏輯函式
from functions.geminiChatFunction import start_new_search_session, search_with_structured_generation

# 初始化 FastAPI 的 APIRouter
router = APIRouter(prefix="/chat", tags=["AI 結構化搜尋"])

# ===================================================================
# == Pydantic 模型 (定義 API 的資料結構)
# ===================================================================

class ChatStartResponse(BaseModel):
    """開始對話時的回應格式"""
    session_id: str
    message: str

class ChatRequest(BaseModel):
    """繼續對話時的請求格式"""
    session_id: str
    message: str

class AttractionInfo(BaseModel):
    """定義回傳給前端的景點資訊中，應該包含哪些欄位"""
    id: str
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    town: Optional[str] = None
    main_image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    # 您可以根據需求，從資料庫模型中加入更多想回傳給前端的欄位

class SearchResponse(BaseModel):
    """搜尋景點成功時的最終回應格式"""
    session_id: str
    attractions: List[AttractionInfo]


# ===================================================================
# == API 端點 (Endpoints)
# ===================================================================

@router.post("/start", response_model=ChatStartResponse, summary="開始一個新的景點搜尋對話")
async def start_search():
    """
    這個端點用來啟動一個全新的對話。
    它會建立一個唯一的 session_id，並回傳固定的開場白，引導使用者開始描述景點。
    """
    session_id = str(uuid.uuid4())
    first_message = await start_new_search_session(session_id)
    return {"session_id": session_id, "message": first_message}


@router.post("/structured-search", response_model=SearchResponse, summary="讓 AI 生成結構化資料並搜尋")
async def structured_search(request: ChatRequest):
    """
    這是核心的搜尋端點。
    它會讓 AI 根據對話歷史和使用者最新的描述，直接生成 5 個最相關景點的完整資料，
    然後在後端資料庫中查找或建立它們，最終回傳這 5 個景點在資料庫中的完整紀錄。
    """
    if not request.session_id or not request.message:
        raise HTTPException(status_code=400, detail="session_id 和 message 為必要欄位")
        
    response_data = await search_with_structured_generation(request.session_id, request.message)
    
    # 檢查後端邏輯是否回傳了錯誤
    if "error" in response_data:
         # 如果 AI 或資料庫處理失敗，回傳 500 伺服器內部錯誤
         raise HTTPException(status_code=500, detail=response_data["error"])
        
    # 如果成功，將 session_id 和後端處理好的 attractions 列表一起回傳
    return {"session_id": request.session_id, **response_data}
# router/data.py

from fastapi import APIRouter, HTTPException

from functions.supabaseFunction import (
    get_random_attraction_from_city,
    get_popular_attractions,
    get_attraction_details,
)

router = APIRouter(prefix="/attractions", tags=["Attractions API"])


@router.get("/random", summary="1. 隨機取得一個景點")
async def get_random_attraction_route(city: str):
    """
    根據城市名稱，隨機回傳一個景點的詳細資訊。
    - **city**: (必要) 城市名稱，("臺"要大寫)，例如 "臺北市", "臺中市", "臺南市"。
    """
    response = get_random_attraction_from_city(city_name=city)
    
    if not response.data:
        raise HTTPException(
            status_code=404, 
            detail=f"在 '{city}' 中找不到任何景點"
        )
        
    return response.data[0]


@router.get("/popular", summary="2. 取得熱門景點列表 (支援分頁)")
async def get_popular_attractions_route(limit: int = 10, offset: int = 0):
    """
    回傳熱門景點列表。如果沒有熱門資料，則回傳最新景點。
    支援分頁功能，方便前端實現「無限滾動」或「載入更多」。
    - **limit**: 每頁回傳的資料筆數，預設 10。
    - **offset**: 要跳過的資料筆數，預設 0 (從頭開始)。
    """
    response = get_popular_attractions(limit=limit, offset=offset)
    return response.data


@router.get("/{attraction_id}", summary="3. 取得景點詳細資訊")
async def get_attraction_detail_route(attraction_id: str):
    """
    使用景點的唯一 ID 來取得其完整的詳細資訊。
    """
    response = get_attraction_details(attraction_id=attraction_id)
    
    if not response.data:
         raise HTTPException(status_code=404, detail="找不到該景點")
         
    return response.data
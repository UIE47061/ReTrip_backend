# router/itineraries.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# --- 導入需要的 Supabase 函式 ---
from functions.supabaseFunction import (
    create_itinerary,
    get_user_itineraries,
    get_user_itinerary_by_id,
    update_user_itinerary,
    delete_user_itinerary,
)

# --- 初始化 Router ---
router = APIRouter(prefix="/itineraries", tags=["Itineraries API"])

# ===================================================================
# == Pydantic 模型 (用於請求和回應的資料驗證)
# ===================================================================

class ItineraryCreate(BaseModel):
    user_id: str
    name: str
    description: Optional[str] = None

class ItineraryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ===================================================================
# == 行程 API 端點 (完整的 CRUD)
# ===================================================================

@router.post("/", summary="建立新行程", status_code=201)
async def create_new_itinerary(itinerary_data: ItineraryCreate):
    response = create_itinerary(
        user_id=itinerary_data.user_id,
        name=itinerary_data.name,
        description=itinerary_data.description
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="建立行程失敗")
    return response.data[0]


@router.get("/{user_id}", summary="取得指定使用者的所有行程")
async def get_user_itineraries_route(user_id: str):
    response = get_user_itineraries(user_id=user_id)
    return response.data


@router.get("/{user_id}/{itinerary_id}", summary="取得單一行程的詳細資訊")
async def get_single_itinerary_route(user_id: str, itinerary_id: int):
    response = get_user_itinerary_by_id(user_id=user_id, itinerary_id=itinerary_id)
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到該行程")
    return response.data


@router.put("/{user_id}/{itinerary_id}", summary="更新行程")
async def update_itinerary_route(
    user_id: str,
    itinerary_id: int,
    itinerary_data: ItineraryUpdate
):
    response = update_user_itinerary(
        user_id=user_id,
        itinerary_id=itinerary_id,
        name=itinerary_data.name,
        description=itinerary_data.description
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到行程或更新失敗")
    return response.data[0]


@router.delete("/{user_id}/{itinerary_id}", summary="刪除行程", status_code=204)
async def delete_itinerary_route(user_id: str, itinerary_id: int):
    response = delete_user_itinerary(user_id=user_id, itinerary_id=itinerary_id)
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到行程或刪除失敗")
    return
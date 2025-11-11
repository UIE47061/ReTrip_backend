# router/itineraries.py

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List

# --- 導入需要的 Supabase 函式 ---
from functions.supabaseFunction import (
    create_itinerary,
    get_user_itineraries,
    get_user_itinerary_by_id,
    update_user_itinerary,
    delete_user_itinerary,
    supabase # 用於身份驗證
)

# --- 初始化 Router ---
router = APIRouter(prefix="/itineraries", tags=["Itineraries API"])

# ===================================================================
# == Pydantic 模型 (用於請求和回應的資料驗證)
# ===================================================================

class ItineraryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ItineraryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

# ===================================================================
# == 身份驗證依賴項 (門禁讀卡機)
# ===================================================================

async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="無效的認證標頭")
    token = authorization.split(" ")[1]
    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if not user:
             raise HTTPException(status_code=401, detail="無效的 token")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token 驗證失敗或已過期")


# ===================================================================
# == 行程 API 端點 (完整的 CRUD)
# ===================================================================

@router.post("/", summary="建立新行程", status_code=201)
async def create_new_itinerary(itinerary_data: ItineraryCreate, current_user = Depends(get_current_user)):
    response = create_itinerary(
        user_id=current_user.id,
        name=itinerary_data.name,
        description=itinerary_data.description
    )
    if not response.data:
        raise HTTPException(status_code=400, detail="建立行程失敗")
    return response.data[0]


@router.get("/me", summary="取得我的所有行程")
async def get_my_itineraries_route(current_user = Depends(get_current_user)):
    response = get_user_itineraries(user_id=current_user.id)
    return response.data


@router.get("/{itinerary_id}", summary="取得單一行程的詳細資訊")
async def get_my_single_itinerary_route(itinerary_id: int, current_user = Depends(get_current_user)):
    response = get_user_itinerary_by_id(user_id=current_user.id, itinerary_id=itinerary_id)
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到該行程或權限不足")
    return response.data


@router.put("/{itinerary_id}", summary="更新我的行程")
async def update_my_itinerary_route(
    itinerary_id: int,
    itinerary_data: ItineraryUpdate,
    current_user = Depends(get_current_user)
):
    response = update_user_itinerary(
        user_id=current_user.id,
        itinerary_id=itinerary_id,
        name=itinerary_data.name,
        description=itinerary_data.description
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到行程或權限不足以更新")
    return response.data[0]


@router.delete("/{itinerary_id}", summary="刪除我的行程", status_code=204)
async def delete_my_itinerary_route(itinerary_id: int, current_user = Depends(get_current_user)):
    response = delete_user_itinerary(user_id=current_user.id, itinerary_id=itinerary_id)
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到行程或權限不足以刪除")
    return
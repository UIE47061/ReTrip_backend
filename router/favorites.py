# router/favorites.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# --- 導入需要的 Supabase 函式 ---
from functions.supabaseFunction import (
    add_favorite,
    remove_favorite,
    get_user_favorites,
)

# --- 初始化 Router ---
router = APIRouter(prefix="/favorites", tags=["Favorites API"])

# ===================================================================
# == Pydantic 模型 (用於請求驗證)
# ===================================================================

class FavoriteRequest(BaseModel):
    user_id: str
    attraction_id: str


# ===================================================================
# == 收藏 API 端點
# ===================================================================

@router.post("/", summary="新增收藏景點", status_code=201)
async def add_favorite_route(favorite_data: FavoriteRequest):
    """
    為指定使用者新增一個收藏景點
    """
    try:
        response = add_favorite(
            user_id=favorite_data.user_id,
            attraction_id=favorite_data.attraction_id
        )
        if not response.data:
            raise HTTPException(status_code=400, detail="新增收藏失敗")
        return {"message": "成功新增收藏", "data": response.data[0]}
    except Exception as e:
        # 處理重複收藏的情況
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail="此景點已經在收藏清單中")
        raise HTTPException(status_code=400, detail=f"新增收藏失敗: {str(e)}")


@router.delete("/", summary="移除收藏景點", status_code=200)
async def remove_favorite_route(favorite_data: FavoriteRequest):
    """
    移除指定使用者的收藏景點
    """
    response = remove_favorite(
        user_id=favorite_data.user_id,
        attraction_id=favorite_data.attraction_id
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="找不到該收藏或移除失敗")
    return {"message": "成功移除收藏"}


@router.get("/{user_id}", summary="取得使用者的所有收藏景點")
async def get_user_favorites_route(user_id: str):
    """
    取得指定使用者的所有收藏景點列表
    """
    response = get_user_favorites(user_id=user_id)
    return response.data

# functions/supabaseFunction.py

from supabase import create_client, Client
from util.config import env

supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)


def get_random_attraction_from_city(city_name: str):
    """
    從資料庫中隨機取得一個指定城市的景點。
    透過呼叫自訂的 SQL 函式 (RPC) 'get_random_attraction_by_city' 來實現。
    """
    return supabase.rpc('get_random_attraction_by_city', {'target_city': city_name}).execute()


def get_popular_attractions(limit: int, offset: int):
    """
    從 popular_attractions_view 取得熱門景點，並支援分頁。
    如果 view 為空，則回傳最新的景點作為備案 (Fallback)，同樣支援分頁。
    """

    popular_response = supabase.from_('popular_attractions_view').select('*').range(offset, offset + limit - 1).execute()

    if popular_response.data:
        return popular_response
    else:
        return get_latest_attractions_paginated(limit=limit, offset=offset)


def get_attraction_details(attraction_id: str):
    """
    取得單一景點的詳細資訊。
    """
    # .single() 確保只回傳一個物件，而不是一個列表
    return supabase.table('attractions').select('*').eq('id', attraction_id).single().execute()


# --- 輔助函式 ---
def get_latest_attractions_paginated(limit: int, offset: int):
    """
    輔助函式：取得最新的景點，並支援分頁。
    專門用於 get_popular_attractions 的備案 (Fallback) 情況。
    """
    return supabase.table('attractions').select('id, name, city, town, main_image_url, description').order('created_at', desc=True).range(offset, offset + limit - 1).execute()
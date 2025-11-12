# functions/supabaseFunction.py

from supabase import create_client, Client
from util.config import env
import google.generativeai as genai
import requests

supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

# 初始化 Gemini API
genai.configure(api_key=env.GOOGLE_API_KEY)

# ===================================================================
# == 使用 Gemini 進行語意搜尋的景點功能
# ===================================================================
def semantic_search_attractions(query_text: str) -> list[dict]:
    """
    接收一段自然語言描述，轉換為 embedding，並在資料庫中尋找語意最相似的景點。
    """
    try:
        # 1. 將查詢文字轉換為 embedding
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=query_text,
            task_type="RETRIEVAL_QUERY"
        )
        query_embedding = result['embedding']

        # 2. 呼叫資料庫函式，使用 text casting 來避免類型錯誤
        matches = supabase.rpc('match_attractions', {
            'query_embedding': query_embedding,
            'match_threshold': 0.3,  # 降低門檻以獲得更多結果
            'match_count': 5         # 固定回傳 5 個
        }).execute()

        # 3. 處理回傳結果，確保 id 是字串格式
        if matches.data:
            for item in matches.data:
                if 'id' in item and item['id'] is not None:
                    item['id'] = str(item['id'])
        
        return matches.data if matches.data else []
    except Exception as e:
        print(f"語意搜尋時發生錯誤: {e}")
        # 如果 RPC 失敗，嘗試直接查詢表格作為備用方案
        try:
            fallback = supabase.table('attractions').select('id, name, city, town, main_image_url, description').limit(5).execute()
            if fallback.data:
                for item in fallback.data:
                    if 'id' in item and item['id'] is not None:
                        item['id'] = str(item['id'])
                return fallback.data
        except Exception as fallback_error:
            print(f"備用查詢也失敗: {fallback_error}")
        return []
    
# --- Google 搜尋工具函式 ---
def google_search_for_attraction(query_text: str):
    """
    【Gemini 要使用的第二個工具】
    當內部資料庫搜尋找不到結果，或使用者查詢非常通用時，
    使用 Google 搜尋來尋找可能的景點或地點。
    """
    try:
        GOOGLE_API_KEY = env.GOOGLE_API_KEY
        SEARCH_ENGINE_ID = env.GOOGLE_SEARCH_ENGINE_ID

        url = f"https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY,
            'cx': SEARCH_ENGINE_ID,
            'q': query_text,
            'num': 5 # 只取前 5 個結果
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status() # 如果請求失敗會拋出錯誤
        
        search_results = response.json().get('items', [])
        
        # 清理並只回傳我們需要的資訊
        cleaned_results = [
            {
                "title": item.get('title'),
                "link": item.get('link'),
                "snippet": item.get('snippet')
            }
            for item in search_results
        ]
        return cleaned_results

    except Exception as e:
        return f"Google 搜尋時發生錯誤: {e}"
    
# ===================================================================
# == 甭身分驗證就能使用的景點查詢功能
# ===================================================================

def get_random_attraction_from_city(city_name: str):
    """
    從資料庫中隨機取得一個指定城市的景點。
    透過呼叫自訂的 SQL 函式 (RPC) 'get_random_attraction_by_city' 來實現。
    """
    return supabase.rpc('get_random_attraction_by_city', {'target_city': city_name}).execute()


def get_random_attraction_with_image_from_city(city_name: str):
    """
    從指定城市中隨機取得一個有圖片（main_image_url 非空）的景點。
    實作方式：先抓出符合條件的 id 列表，再在 Python 端隨機選一個 id，最後回傳該景點的完整資料。
    如果沒有符合條件的景點，回傳一個空的 response 物件（含 .data = []），以便上層路由處理 404。
    """
    try:
        # 先從 DB 取得該 city 的 id 與 main_image_url，之後在 Python 端過濾出有圖片的項目
        resp = supabase.table('attractions').select('id, main_image_url').eq('city', city_name).execute()
        ids = [r.get('id') for r in (resp.data or []) if r.get('id') and r.get('main_image_url')]

        if not ids:
            class EmptyResp:
                data = []
            return EmptyResp()

        import random
        chosen_id = str(random.choice(ids))

        detail = supabase.table('attractions').select('*').eq('id', chosen_id).limit(1).execute()
        return detail
    except Exception as e:
        print(f"get_random_attraction_with_image_from_city 發生錯誤: {e}")
        class EmptyResp:
            data = []
        return EmptyResp()


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
    return supabase.table('attractions').select('*').eq('id', attraction_id).single().execute()


def get_multiple_attractions_details(attraction_ids: list[str]):
    """
    取得多個景點的詳細資訊。
    接收一個景點 ID 列表，回傳所有匹配的景點資料。
    """
    if not attraction_ids:
        return supabase.table('attractions').select('*').in_('id', []).execute()
    return supabase.table('attractions').select('*').in_('id', attraction_ids).execute()


def get_latest_attractions_paginated(limit: int, offset: int):
    """
    輔助函式：取得最新的景點，並支援分頁。
    專門用於 get_popular_attractions 的備案 (Fallback) 情況。
    """
    return supabase.table('attractions').select('id, name, city, town, main_image_url, description').order('created_at', desc=True).range(offset, offset + limit - 1).execute()

# ===================================================================
# == 使用者個人行程 (Itineraries) - 完整的 CRUD 操作
# ===================================================================

def create_itinerary(user_id: str, name: str, description: str | None):
    """為指定使用者建立一個新的行程"""
    return supabase.table('itineraries').insert({
        'user_id': user_id,
        'name': name,
        'description': description
    }).execute()

def get_user_itineraries(user_id: str):
    """取得指定使用者的所有行程列表"""
    # 按照建立時間倒序排列，最新的在最前面
    return supabase.table('itineraries').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()

def get_user_itinerary_by_id(user_id: str, itinerary_id: int):
    """
    取得一個屬於指定使用者的【單一】行程。
    使用 .match() 確保使用者只能查詢到自己的行程，非常安全。
    """
    return supabase.table('itineraries').select('*').match({
        'id': itinerary_id, 
        'user_id': user_id
    }).single().execute()

def update_user_itinerary(user_id: str, itinerary_id: int, name: str | None, description: str | None):
    """更新一個屬於指定使用者的行程"""
    update_data = {}
    # 只更新有被提供的欄位
    if name is not None:
        update_data['name'] = name
    if description is not None:
        update_data['description'] = description
    
    # .match() 確保我們只更新同時滿足 id 和 user_id 的那一筆資料
    return supabase.table('itineraries').update(update_data).match({
        'id': itinerary_id,
        'user_id': user_id
    }).execute()

def delete_user_itinerary(user_id: str, itinerary_id: int):
    """刪除一個屬於指定使用者的行程"""
    # .match() 同樣確保了使用者只能刪除自己的行程
    return supabase.table('itineraries').delete().match({
        'id': itinerary_id,
        'user_id': user_id
    }).execute()

# ===================================================================
# == 使用者收藏景點 (Favorites) - 新增與刪除
# ===================================================================

def add_favorite(user_id: str, attraction_id: str):
    """為指定使用者新增一個收藏景點"""
    return supabase.table('user_favorites').insert({
        'user_id': user_id,
        'attraction_id': attraction_id
    }).execute()

def remove_favorite(user_id: str, attraction_id: str):
    """移除指定使用者的收藏景點"""
    return supabase.table('user_favorites').delete().match({
        'user_id': user_id,
        'attraction_id': attraction_id
    }).execute()

def get_user_favorites(user_id: str):
    """取得指定使用者的所有收藏景點"""
    return supabase.table('user_favorites').select('*').eq('user_id', user_id).execute()


# ===================================================================
# == 輔助：批次查找或建立景點
# ===================================================================
def find_or_create_attractions_batch(attraction_candidates: list[dict]) -> list[dict]:
    """
    接收由 AI 產生的景點候選清單 (每項包含 name, main_image_url, city, town 等欄位)，
    對每一筆：
      1. 嘗試以 name + city + town 查詢是否已存在（.match() / .eq()），
      2. 若存在，回傳該筆完整資料（含 id），
      3. 若不存在，插入新紀錄並回傳插入後的紀錄（含 id）。

    回傳值：list[dict]，每項包含資料庫中的欄位（id, name, city, town, main_image_url, ...）。
    """
    results = []

    for cand in attraction_candidates:
        name = cand.get('name')
        city = cand.get('city')
        town = cand.get('town')
        main_image_url = cand.get('main_image_url') or cand.get('image') or ''
        description = cand.get('description') if 'description' in cand else None

        # 安全檢查
        if not name:
            continue

        try:
            # 嘗試依照 name + city + town 去找現有紀錄
            query = supabase.table('attractions').select('*').match({
                'name': name,
                'city': city,
                'town': town
            }).single().execute()

            if query.data:
                item = query.data
                # 確保 id 為字串
                if 'id' in item and item['id'] is not None:
                    item['id'] = str(item['id'])
                results.append(item)
                continue

            # 若不存在，插入新紀錄
            insert_payload = {
                'name': name,
                'city': city,
                'town': town,
                'main_image_url': main_image_url
            }
            if description:
                insert_payload['description'] = description

            insert_resp = supabase.table('attractions').insert(insert_payload).execute()
            if insert_resp.data:
                new_item = insert_resp.data[0]
                if 'id' in new_item and new_item['id'] is not None:
                    new_item['id'] = str(new_item['id'])
                results.append(new_item)
            else:
                # 若 insert 沒回傳 data，嘗試再查一次以取得 id
                retry = supabase.table('attractions').select('*').match({
                    'name': name,
                    'city': city,
                    'town': town
                }).single().execute()
                if retry.data:
                    if 'id' in retry.data and retry.data['id'] is not None:
                        retry.data['id'] = str(retry.data['id'])
                    results.append(retry.data)

        except Exception as e:
            print(f"find_or_create 處理 {name} 時發生錯誤: {e}")
            # 繼續處理下一筆，不讓整個批次失敗
            continue

    return results


# ===================================================================
# == 輔助：批次只查詢已存在的景點（不建立）
# ===================================================================
def find_existing_attractions_batch(attraction_candidates: list[dict]) -> list[dict]:
    """
    接收由 AI 產生的景點候選清單 (每項包含 name, city, town 等欄位)，
    僅查詢是否存在於資料庫中（以 name+city+town 為匹配條件）。

    回傳值：list[dict]，只包含在資料庫中找到的紀錄（含 id、name、city、town、main_image_url）。
    """
    results = []

    for cand in attraction_candidates:
        name = cand.get('name')
        city = cand.get('city')
        town = cand.get('town')

        # 安全檢查
        if not name:
            continue

        try:
            # 使用 limit(1) 與 eq 避免 .single() 在無結果時拋出錯誤
            query = supabase.table('attractions').select('id, name, city, town, main_image_url')
            query = query.eq('name', name)
            if city is not None:
                query = query.eq('city', city)
            if town is not None:
                query = query.eq('town', town)
            query = query.limit(1).execute()

            if query.data and isinstance(query.data, list) and len(query.data) > 0:
                item = query.data[0]
                if 'id' in item and item['id'] is not None:
                    item['id'] = str(item['id'])
                results.append(item)
        except Exception as e:
            # 只在非空結果造成的情況之外印出錯誤
            print(f"find_existing 處理 {name} 時發生錯誤: {e}")
            continue

    return results

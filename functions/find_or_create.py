import asyncio
from util.config import env

# --- 初始化 ---
from supabase import create_client, Client
supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

async def find_or_create_attractions_batch(attraction_objects: list[dict]) -> list[dict]:
    """
    在資料庫中批次尋找或建立景點，資料來源是 AI 生成的完整物件。
    返回一個包含所有找到或建立的景點物件的列表。
    """
    if not attraction_objects:
        return []

    names_to_check = [attr.get('name') for attr in attraction_objects if attr.get('name')]
    found_attractions = []
    attractions_to_create = []

    # 步驟 A: 批次搜尋現有景點
    print(f"正在資料庫中批次檢查 {len(names_to_check)} 個景點...")
    query_filter = ','.join([f'name.ilike.%{name}%' for name in names_to_check])
    search_response = await asyncio.to_thread(
        supabase.table('attractions').select('*').or_(query_filter).execute
    )
    
    existing_names = {attr['name'].lower() for attr in search_response.data} if search_response.data else set()

    for attr_obj in attraction_objects:
        if attr_obj.get('name', '').lower() in existing_names:
            # 為了簡單起見，如果名字相似的已存在，我們就直接使用資料庫的版本
            # 這裡可以加入更複雜的更新邏輯
            print(f"景點 '{attr_obj.get('name')}' 已存在於資料庫中。")
            # 找到對應的物件並加入
            for existing_attr in search_response.data:
                if attr_obj.get('name').lower() in existing_attr['name'].lower():
                    found_attractions.append(existing_attr)
                    break
        else:
            print(f"景點 '{attr_obj.get('name')}' 是新的，準備新增。")
            attractions_to_create.append(attr_obj)

    # 步驟 B: 對於 AI 生成的新景點，直接進行批次建立
    if attractions_to_create:
        print(f"正在將 {len(attractions_to_create)} 個新景點新增至資料庫...")
        
        # 清理資料，移除 AI 可能會幻想出來的多餘欄位
        valid_columns = [
            "name", "description", "latitude", "longitude", "city", "town", 
            "street_address", "main_image_url", "website_url", "address_details",
            "images", "telephones", "social_media", "traffic_info", 
            "parking_info", "fee_info"
        ]
        
        clean_attractions_to_insert = []
        for attr in attractions_to_create:
            clean_attr = {key: attr[key] for key in valid_columns if key in attr}
            clean_attractions_to_insert.append(clean_attr)

        insert_response = await asyncio.to_thread(
            supabase.table('attractions').insert(clean_attractions_to_insert).execute
        )
        if insert_response.data:
            found_attractions.extend(insert_response.data)
        else:
            print(f"資料庫插入失敗: {insert_response.error}")
                
    return found_attractions
# tools/enrich_data.py (加入了 tqdm 進度條)

import time
import json
import requests
import google.generativeai as genai
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from util.config import env
from tqdm import tqdm # <-- 1. 導入 tqdm

# --- 初始化 Supabase Client ---
from supabase import create_client, Client
supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

# --- 初始化 Google AI ---
try:
    genai.configure(api_key=env.GOOGLE_API_KEY)
    tagging_model = genai.GenerativeModel('gemini-pro-latest') 
except Exception as e:
    raise RuntimeError(f"Google AI 初始化失敗，請檢查 GOOGLE_API_KEY 是否正確: {e}")

# --- 全域設定 ---
BATCH_SIZE = 50
ALLOWED_TAGS = {
    "地理位置": ["北部", "中部", "南部", "東部", "離島", "山上", "靠海", "市區", "郊區"],
    "景點類型": ["自然景觀", "歷史古蹟", "建築地標", "博物館", "美術館", "主題樂園", "動物園", "植物園", "老街", "夜市", "寺廟教堂", "文創園區", "觀光工廠", "溫泉"],
    "適合對象": ["親子家庭", "情侶約會", "朋友出遊", "獨自旅行", "攝影愛好者", "健行登山客"],
    "活動特色": ["戶外活動", "室內景點", "健行步道", "自行車道", "水上活動", "賞花", "賞鳥", "看夜景", "購物", "以美食聞名"],
    "消費類型": ["免費景點", "需要門票"],
    "設施服務": ["有無障礙設施", "有停車場", "有導覽服務"],
    "氛圍感受": ["寧靜放鬆", "熱鬧繁華", "寓教於樂", "懷舊復古"]
}

# ... (generate_tags_for_attraction 和 find_image_for_attraction 函式保持不變) ...
def generate_tags_for_attraction(name: str, description: str) -> list[str] | None:
    """使用 Gemini 為景點生成結構化標籤"""
    try:
        prompt = f"""
        # 指令
        你的任務是擔任專業的旅遊資料分析師。根據景點的名稱和描述，從提供的「允許的標籤」列表中，精準地選出所有符合的標籤。
        你的回覆必須是、也只能是一個 JSON 格式的陣列，裡面只包含選出的標籤字串。

        # 允許的標籤
        {json.dumps(ALLOWED_TAGS, ensure_ascii=False, indent=2)}

        # 景點資料
        - 名稱: "{name}"
        - 描述: "{description}"

        # 你的 JSON 回覆:
        """
        response = tagging_model.generate_content(prompt)
        tags = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        return tags if isinstance(tags, list) else None
    except Exception as e:
        # 使用 pbar.write 來打印錯誤，才不會打亂進度條
        tqdm.write(f"  └─ 標籤生成失敗: {e}")
        return None

def find_image_for_attraction(name: str) -> str | None:
    """使用 Google Search 為景點尋找一張代表性圖片"""
    try:
        query = f"{name} 台灣 景點"
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': env.GOOGLE_API_KEY,
            'cx': env.GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'searchType': 'image',
            'num': 1,
            'imgSize': 'huge',
            'safe': 'active'
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get('items', [])
        
        if results:
            return results[0].get('link')
        return None
    except requests.exceptions.HTTPError as e:
        tqdm.write(f"  └─ 圖片搜尋 HTTP 錯誤: {e.response.status_code} {e.response.reason}")
        if e.response.status_code in [429, 403]:
            tqdm.write("     └─ 這可能是因為 API 請求頻率過高或每日免費額度已用完。")
        return None
    except Exception as e:
        tqdm.write(f"  └─ 圖片搜尋發生未知錯誤: {e}")
        return None

def enrich_attractions_data():
    """主函式：分頁處理所有需要豐富資料的景點，並顯示進度條"""

    # --- 2. 首先，計算總共有多少筆資料需要處理 ---
    print("正在計算需要處理的景點總數...")
    count_response = supabase.table('attractions').select(
        'id', count='exact' # 使用 'exact' 來獲取精確總數
    ).or_(
        'tags.is.NULL,main_image_url.is.NULL'
    ).execute()
    
    total_to_process = count_response.count
    print(f"總共找到 {total_to_process} 筆景點需要更新。")

    if total_to_process == 0:
        print("所有景點都已處理完畢！")
        return

    page = 0
    total_updated = 0

    # --- 3. 初始化 tqdm 進度條 ---
    with tqdm(total=total_to_process, desc="正在豐富景點資料", unit=" 筆") as pbar:
        while True:
            offset = page * BATCH_SIZE
            
            response = supabase.table('attractions').select(
                'id, name, description, main_image_url, tags'
            ).or_(
                'tags.is.NULL,main_image_url.is.NULL'
            ).range(
                offset, offset + BATCH_SIZE - 1
            ).execute()

            attractions = response.data
            if not attractions:
                break # 當撈不到更多資料時，結束迴圈

            records_to_update = []
            for attr in attractions:
                # 使用 pbar.set_postfix_str 來顯示目前正在處理的項目
                pbar.set_postfix_str(f"處理中: {attr['name'][:20]}...")
                update_payload = {'id': attr['id']}
                
                # --- 處理標籤 ---
                if not attr.get('tags'):
                    tags = generate_tags_for_attraction(attr['name'], attr['description'])
                    if tags:
                        update_payload['tags'] = tags
                        pbar.write(f"  ├─ {attr['name']}: 已生成標籤。")
                    # time.sleep(1)

                # --- 處理圖片 ---
                if not attr.get('main_image_url'):
                    image_url = find_image_for_attraction(attr['name'])
                    if image_url:
                        update_payload['main_image_url'] = image_url
                        pbar.write(f"  ├─ {attr['name']}: 已找到圖片。")
                    time.sleep(1)

                if len(update_payload) > 1:
                    records_to_update.append(update_payload)
                
                # --- 4. 每處理完一筆，就更新進度條 ---
                pbar.update(1)

            if records_to_update:
                upsert_response = supabase.table('attractions').upsert(records_to_update).execute()
                updated_count = len(upsert_response.data)
                total_updated += updated_count
            
            page += 1

    print(f"\n--- ✨ 任務完成 ✨ ---")
    print(f"總共更新了 {total_updated} 筆景點資料。")

if __name__ == "__main__":
    enrich_attractions_data()
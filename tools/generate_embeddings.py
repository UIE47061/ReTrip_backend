# generate_embeddings.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import os
import time
import google.generativeai as genai
from functions.supabaseFunction import supabase

# --- 設定 ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY 環境變數未設定！")
genai.configure(api_key=GOOGLE_API_KEY)

# 定義每一批次處理的大小
BATCH_SIZE = 500

def generate_and_store_embeddings():
    page = 0
    total_processed = 0

    while True:
        print(f"\n--- 正在處理第 {page + 1} 批次 (每批 {BATCH_SIZE} 筆) ---")
        
        # 1. 使用 .range() 來分頁取得資料
        offset = page * BATCH_SIZE
        response = supabase.table('attractions').select(
            'id, name, description'
        ).is_(
            'embedding', None
        ).range(
            offset, offset + BATCH_SIZE - 1
        ).execute()

        attractions = response.data
        if not attractions:
            print("所有需要處理的景點都已完成！")
            break

        print(f"找到 {len(attractions)} 個景點需要生成 embedding...")

        # 2. 準備要進行 embedding 的文本
        texts_to_embed = [
            f"景點名稱: {attr['name']}. 描述: {attr['description']}"
            for attr in attractions
        ]

        # 3. 呼叫 Gemini 的 embedding 模型
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=texts_to_embed,
                task_type="RETRIEVAL_DOCUMENT"
            )
            embeddings = result['embedding']
        except Exception as e:
            print(f"!! 呼叫 Google AI API 時發生錯誤: {e}")
            print("!! 可能是因為請求頻率過高，等待 10 秒後重試...")
            time.sleep(10)
            continue # 跳過這次迴圈，下次會重試同一批資料

        # 4. 將生成的 embedding 更新回 Supabase
        updates = []
        for i, attr in enumerate(attractions):
            updates.append({
                'id': attr['id'],
                'embedding': embeddings[i]
            })
        
        upsert_response = supabase.table('attractions').upsert(updates).execute()
        
        processed_count = len(upsert_response.data)
        total_processed += processed_count
        print(f"成功為 {processed_count} 個景點更新了 embedding。")

        # 前進到下一頁
        page += 1
        
        # 為了避免觸發 Google API 的速率限制，每次處理完一批後稍微等待一下
        time.sleep(1)

    print(f"\n--- 處理完成 ---")
    print(f"總共處理了 {total_processed} 個景點。")

if __name__ == "__main__":
    generate_and_store_embeddings()
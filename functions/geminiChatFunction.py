# functions/geminiChatFunction.py (最終完整修正版)

import json
import asyncio
import google.generativeai as genai
from util.config import env
from .find_or_create import find_or_create_attractions_batch

# --- 初始化 ---
from supabase import create_client, Client
supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

genai.configure(api_key=env.GOOGLE_API_KEY)

# 啟用 JSON 模式
generation_config = genai.types.GenerationConfig(
    response_mime_type="application/json"
)
chat_model = genai.GenerativeModel(
    'gemini-pro-latest',
    generation_config=generation_config
)

# --- 核心邏輯函式 ---

async def start_new_search_session(session_id: str) -> str:
    """
    開始一個新的搜尋對話，並回傳固定的開場白。
    """
    opening_message = "你想要找之前去過的那個地方嗎～ 形容一下那邊的景色吧！"
    await asyncio.to_thread(
        supabase.table('chat_sessions').insert({"session_id": session_id, "history": []}).execute
    )
    return opening_message

async def search_with_structured_generation(session_id: str, user_message: str) -> dict:
    """
    讓 AI 根據對話，直接生成 5 個最相關景點的完整資料，並在資料庫中查找或建立它們。
    """
    # ▼▼▼ 這裡就是修正的部分：將 ... 替換為實際的程式碼 ▼▼▼
    # 步驟 1: 從資料庫讀取歷史紀錄
    result = await asyncio.to_thread(
        supabase.table('chat_sessions').select('history').eq('session_id', session_id).single().execute
    )
    # ▲▲▲ 這裡就是修正的部分 ▲▲▲
    
    if not result.data:
        return {"error": "找不到此對話，可能已過期或無效。"}

    saved_history = result.data.get('history', [])
    history_context = "\n".join([f"{'使用者' if msg['role'] == 'user' else 'AI'}: {msg['parts'][0]}" for msg in saved_history])

    # --- 步驟 2: 定義我們期望的 JSON Schema ---
    json_schema = {
        "type": "object",
        "properties": {
            "attractions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "景點的準確中文全名"},
                        "description": {"type": "string", "description": "一段約 50-100 字的繁體中文景點描述"},
                        "latitude": {"type": "number", "description": "緯度座標"},
                        "longitude": {"type": "number", "description": "經度座標"},
                        "city": {"type": "string", "description": "景點所在的縣市，例如 '臺北市'"},
                        "town": {"type": "string", "description": "景點所在的鄉鎮市區，例如 '信義區'"},
                        "main_image_url": {"type": "string", "description": "一張代表性圖片的公開 URL。如果找不到，請留空字串。"}
                    },
                    "required": ["name", "description", "latitude", "longitude", "city", "town"]
                }
            }
        },
        "required": ["attractions"]
    }

    # --- 步驟 3: 建構 Prompt ---
    prompt = f"""
    # 角色
    你是一位資料庫工程師，專長是從非結構化資訊中提取資料並填入資料庫。

    # 任務
    根據以下對話歷史和使用者最新的問題，找出 5 個最有可能的台灣景點，並為每一個景點生成一份符合指定 JSON Schema 的完整資料。

    # 對話歷史
    {history_context}

    # 使用者最新問題
    {user_message}

    # 規則
    - 你的回答必須是、也只能是一個完全符合以下 JSON Schema 的 JSON 物件。
    - 所有欄位的內容都必須基於你龐大的內部知識庫進行填充。
    - 所有文字都必須是繁體中文。
    - 如果某些資訊（例如 main_image_url）找不到，請填寫 null 或空字串。

    # JSON Schema 範本:
    {json.dumps(json_schema, ensure_ascii=False, indent=2)}

    # 你的 JSON 回覆:
    """
    
    print("正在請求 Gemini 進行結構化資料生成...")
    try:
        response = await chat_model.generate_content_async(prompt)
        generated_data = json.loads(response.text)
        guessed_attractions = generated_data.get("attractions", [])
        
        if not isinstance(guessed_attractions, list):
            raise ValueError("AI 回應的 attractions 不是一個列表")
            
        print(f"AI 成功生成 {len(guessed_attractions)} 筆結構化資料。")
    except (json.JSONDecodeError, ValueError, Exception) as e:
        print(f"解析或生成 AI 回應時失敗: {e}")
        return {"error": "AI 回應格式不正確或發生內部錯誤，請稍後再試。"}

    # 步驟 4: 批次處理函式
    attraction_data_list = await find_or_create_attractions_batch(guessed_attractions)

    # 步驟 5: 更新對話歷史
    new_user_part = {'role': 'user', 'parts': [{'text': user_message}]}
    names_for_history = [attr.get('name', '未知景點') for attr in guessed_attractions]
    new_model_part = {'role': 'model', 'parts': [{'text': f"根據你的描述，我找到了這些可能的景點: {', '.join(names_for_history)}"}]}
    saved_history.extend([new_user_part, new_model_part])
    
    await asyncio.to_thread(
        supabase.table('chat_sessions').update({"history": saved_history}).eq('session_id', session_id).execute
    )
    
    # 步驟 6: 回傳最終結果
    return {"attractions": attraction_data_list}
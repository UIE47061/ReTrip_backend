# functions/geminiChatFunction.py

import json
import time
import os
import google.generativeai as genai
from util.config import env
from .supabaseFunction import find_or_create_attractions_batch

# 初始化 Gemini
genai.configure(api_key=env.GOOGLE_API_KEY)
generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
chat_model = genai.GenerativeModel('gemini-2.5-pro', generation_config=generation_config)

FAST_CHAT_MODEL = os.getenv('FAST_CHAT_MODEL', 'models/gemini-flash-latest')
fast_text_model = genai.GenerativeModel(FAST_CHAT_MODEL)

try:
    if isinstance(fast_text_model, str):
        fast_text_model = genai.GenerativeModel(fast_text_model)
except Exception as e:
    print(f"fast_text_model 初始化失敗，回退至 chat_model：{e}")
    fast_text_model = chat_model

# 簡單的 in-memory cache（message -> (answer, timestamp)），TTL 可由 env 控制
CHAT_CACHE_TTL = int(os.getenv('CHAT_CACHE_TTL', '60'))
_chat_cache: dict = {}

# 簡短問候的快速回覆清單
_greeting_set = set(['hi', 'hello', '嗨', '哈囉', '你好'])


async def search_with_gemini_candidates(user_message: str) -> dict:
    """
    讓 Gemini 直接思考並回傳最多 5 個候選景點（每項包含 name, city, town, main_image_url），
    接著確認資料庫：若不存在則新增並回傳最終的資料庫紀錄（含 id）。

    回傳格式:
    {"attractions": [ {id, name, city, town, main_image_url}, ... ] }
    """
    # Prompt 要求：只回傳 JSON，並使用繁體中文
    prompt = f"""
    請你扮演一位資深旅遊專家與地理資料檢索員，根據使用者的描述直接列出最多 5 個最可能的台灣景點候選。
    請只回傳一個 JSON 物件，格式如下：
    {{"attractions":[{{"name":"...","city":"...","town":"...","main_image_url":"..."}}, ...]}}
    - 所有文字請使用繁體中文。
    - 如果某個欄位找不到資料，請填空字串("")。
    - 陣列長度最多 5，至少 1。

    描述如果是高高的塔根紅色的樹 => "無極真元天壇(天元宮)"

    使用者描述：""" + user_message + """
    """

    try:
        response = await chat_model.generate_content_async(prompt)
        generated_text = response.text
        # 解析 JSON
        data = json.loads(generated_text)
        candidates = data.get('attractions', [])

        # 驗證資料形狀
        if not isinstance(candidates, list):
            return {"error": "AI 回傳格式不正確 (attractions 不是列表)"}

        # 只保留必要欄位並標準化鍵名
        normalized = []
        for c in candidates[:5]:
            if not isinstance(c, dict):
                continue
            normalized.append({
                'name': c.get('name','').strip(),
                'city': c.get('city','').strip(),
                'town': c.get('town','').strip(),
                'main_image_url': c.get('main_image_url','').strip()
            })

        if not normalized:
            return {"attractions": [], "message": "AI 未回傳候選景點。"}

        # 呼叫批次查詢（僅查詢已存在的景點，不建立新紀錄）
        from .supabaseFunction import find_existing_attractions_batch
        db_results = find_existing_attractions_batch(normalized)

        # 建立 lookup map 以便依候選順序回傳 ids
        lookup = {}
        for r in db_results:
            key = ( (r.get('name') or '').strip().lower(), (r.get('city') or '').strip().lower(), (r.get('town') or '').strip().lower() )
            lookup[key] = r

        ids = []
        for cand in normalized:
            key = ( (cand.get('name') or '').strip().lower(), (cand.get('city') or '').strip().lower(), (cand.get('town') or '').strip().lower() )
            found = lookup.get(key)
            if found and found.get('id') is not None:
                ids.append(str(found.get('id')))
            else:
                # 如果找不到，回傳空字串以保留位置 (前端可辨識為未命中)
                ids.append("")

        return {"ids": ids, "found": db_results}

    except Exception as e:
        print(f"Gemini 生成或後續處理失敗: {e}")
        return {"error": f"處理失敗: {str(e)}"}


async def chat_travel_question(user_message: str) -> dict:
    """
    純 chat API：針對使用者的旅遊相關問題直接回覆一段繁體中文文字回答。
    回傳格式：{"answer": "..."}
    """
    try:
        key = user_message.strip().lower()

        # 快速短路：極短問候直接本地回覆，避免呼叫模型
        if key in _greeting_set or (len(key) <= 6 and any(g in key for g in _greeting_set)):
            return {"answer": "嗨！有什麼關於旅遊的問題我可以幫你解答的呢？"}

        # 檢查快取
        cached = _chat_cache.get(key)
        if cached:
            answer, ts = cached
            if time.time() - ts < CHAT_CACHE_TTL:
                return {"answer": answer}
            else:
                del _chat_cache[key]

        prompt = (
            "你是一位友善且實用的台灣旅遊助理。使用繁體中文，簡潔且直接回答使用者的問題。"
            + "\n使用者: " + user_message + "\n回覆:"
        )

        # 使用較快的 model 以降低延遲
        resp = await fast_text_model.generate_content_async(prompt)
        answer = resp.text.strip() if getattr(resp, 'text', None) is not None else str(resp)

        # 存入快取
        try:
            _chat_cache[key] = (answer, time.time())
        except Exception:
            pass

        return {"answer": answer}
    except Exception as e:
        print(f"chat_travel_question 發生錯誤: {e}")
        return {"error": str(e)}


async def generate_attraction_tags(attraction_name: str) -> dict:
    """
    接收景點名稱（例如 "台北101"），回傳三個短標籤 (tags)。
    回傳格式：{"tags": ["標籤1","標籤2","標籤3"]}
    """
    try:
        prompt = (
            "請以繁體中文，為這個台灣景點產生三個簡短、有吸引力的標籤（tag）。"
            + " 只回傳一個 JSON 物件，格式如下：{\"tags\":[\"標籤1\",\"標籤2\",\"標籤3\"]}。"
            + " 景點名稱: " + attraction_name
        )
        # 使用較快的 model 產生 tags（較不需要 pro model）
        model_to_use = fast_text_model if hasattr(fast_text_model, 'generate_content_async') else chat_model
        resp = await model_to_use.generate_content_async(prompt)
        text = getattr(resp, 'text', '') or str(resp)

        # 嘗試解析 JSON；若失敗，嘗試用簡單分隔符號擷取
        tags = []
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                tags = data.get('tags', [])
        except Exception:
            # 非 JSON 回傳，嘗試以逗號或換行分隔並取前 3 個
            cleaned = text.strip().strip('"')
            if ',' in cleaned:
                tags = [t.strip() for t in cleaned.split(',') if t.strip()][:3]
            else:
                lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
                if lines:
                    if len(lines) == 1 and ':' in lines[0]:
                        parts = lines[0].split(':', 1)[1]
                        tags = [t.strip() for t in parts.replace(';', ',').split(',') if t.strip()][:3]
                    else:
                        tags = lines[:3]

        if isinstance(tags, list):
            tags = [str(t).strip() for t in tags][:3]
        else:
            tags = []

        return {"tags": tags}
    except Exception as e:
        print(f"generate_attraction_tags 發生錯誤: {e}")
        return {"error": str(e)}

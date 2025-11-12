# gemini_agent.py


import google.generativeai as genai
from util.config import env

from functions.supabaseFunction import (
    semantic_search_attractions,
    google_search_for_attraction
)

# ===================================================================
# == 初始化與設定
# ===================================================================

try:
    GOOGLE_API_KEY = env.GOOGLE_API_KEY
    if not GOOGLE_API_KEY:
        raise AttributeError
except AttributeError:
    raise ValueError("在 config 中找不到 GOOGLE_API_KEY，請檢查您的 .env 檔案或環境變數。")

genai.configure(api_key=GOOGLE_API_KEY)


# --- 2. 定義 Agent 可用的工具 ---
# 這是 Agent 的「能力清單」，它會根據使用者問題和工具描述來決定使用哪個
tool_definitions = [
    {
        "name": "semantic_search_attractions",
        "description": "優先使用此工具！用於在我們的內部景點資料庫中進行語意搜尋。適合處理使用者用模糊、描述性的語言尋找特定景點的情況，例如描述景點的外觀、特徵或感受。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query_text": {
                    "type": "STRING",
                    "description": "使用者用來描述景點的完整、未經修改的自然語言句子。例如：'我去過一個地方在山上，那裏有紅色的樹和圓形的高塔'"
                }
            },
            "required": ["query_text"]
        }
    },
    {
        "name": "google_search_for_attraction",
        "description": "當『內部景點資料庫搜尋』(semantic_search_attractions) 找不到任何結果、結果不相關或信心度很低時，使用此工具作為備案。也可用於查詢非常通用、需要即時資訊或資料庫中可能不存在的地點。",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query_text": {
                    "type": "STRING",
                    "description": "要進行 Google 搜尋的查詢字詞。應該基於使用者的原始問題，提煉出最核心的關鍵字。例如：'市中心 很高的 玻璃盒子 建築 藝術品'"
                }
            },
            "required": ["query_text"]
        }
    }
]


# --- 3. 初始化 Gemini 模型 ---
# 將我們的工具清單提供給模型
model = genai.GenerativeModel(
    model_name='gemini-pro-latest', # 使用一個穩定且支援 function calling 的模型
    tools=tool_definitions
)


# ===================================================================
# == Agent 主邏輯
# ===================================================================

def run_agent(user_prompt: str, max_turns: int = 5):
    """
    執行 AI Agent，強制其自主完成多輪工具呼叫，直到找到最終答案為止。
    """
    print(f"使用者: {user_prompt}\n")
    
    chat = model.start_chat()
    
    # --- 這是我們精心設計的、更嚴格的初始指令 ---
    prompt = f"""
    # 指令區塊
    - 你的角色是一位專業、沉默寡言的台灣旅遊景點分析員。
    - **你的唯一任務是找到使用者問題的答案**。
    - **絕對禁止**在找到最終答案前回覆任何中間過程或意圖。
    - 所有最終回覆都必須使用【繁體中文】。

    # 任務與策略
    - 使用者的問題是：「{user_prompt}」
    - **執行策略**：
        1. 你必須先使用 `semantic_search_attractions` 工具。
        2. 檢查上一步的結果。如果結果為空或明顯不符，你的下一步**必須**是呼叫 `google_search_for_attraction` 工具。不准回覆文字。
        3. 只有在你已經呼叫完所有必要的工具，並且有信心給出一個具體答案時，你才能生成最終的文字回覆。
    - 開始執行任務。
    """
    
    response = chat.send_message(prompt)
    
    for turn in range(max_turns):
        print(f"--- AI 思考回合 {turn + 1} ---")
        
        try:
            function_call = response.candidates[0].content.parts[0].function_call
            if not hasattr(function_call, 'name') or not function_call.name:
                break 
        except (IndexError, AttributeError):
            break

        tool_name = function_call.name
        print(f"AI 決定使用工具: {tool_name}")

        tool_results = None

        if tool_name == "semantic_search_attractions":
            query = function_call.args.get('query_text', user_prompt)
            tool_results = semantic_search_attractions(query)
            print(f"內部搜尋結果: {tool_results}")

        elif tool_name == "google_search_for_attraction":
            query = function_call.args.get('query_text', user_prompt)
            tool_results = google_search_for_attraction(query)
            print(f"Google 搜尋結果: {tool_results}")
        
        else:
            tool_results = {"status": "錯誤", "error": f"未知的工具: {tool_name}"}

        print("將結果回報給 AI，等待下一步指令...")
        response = chat.send_message({
            "function_response": {
                "name": tool_name,
                "response": {
                    "results": tool_results,
                },
            },
        })

    # --- 當迴圈結束時，從最終的回應中提取純文字並打印 ---
    try:
        final_response = response.candidates[0].content.parts[0].text
    except (IndexError, AttributeError):
        final_response = "抱歉，我目前遇到一些技術問題，暫時無法回覆。"
        
    print(f"\n=====================================")
    print(f"AI 最終回覆:\n{final_response}")
    print(f"=====================================")



# ===================================================================
# == 程式執行入口
# ===================================================================

if __name__ == "__main__":
    # 您可以在這裡測試不同的使用者問題
    test_prompt_1 = "我去過一個地方在市中心，那裏有一個很高的建築，外觀像是一個大玻璃盒子，裡面有很多藝術品展示。你能幫我找出這是什麼景點嗎？"
    test_prompt_2 = "我想找一個在山上，可以看到海，而且適合情侶約會的地方。"
    test_prompt_3 = "金門有什麼推薦的戰地景點？"

    run_agent(test_prompt_1)
# check.py
# 目的：這是一個健康檢查腳本，用於驗證您的專案環境配置是否能成功連接到 Google AI 服務。

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from util.config import env
    print("✅ 步驟 1/4: 成功導入 `util.config` 模組。")
except (ModuleNotFoundError, ImportError) as e:
    print("❌ 錯誤：找不到 `util.config` 模組。")
    print(f"   詳細錯誤: {e}")
    print("   請確認您是在專案的根目錄 (ReTrip_backend) 下執行此腳本，或者您的 Python 路徑設定正確。")
    sys.exit(1) # 程式無法繼續，退出

# --- 步驟 2: 檢查 .env 檔案與 GOOGLE_API_KEY ---
try:
    GOOGLE_API_KEY = env.GOOGLE_API_KEY
    if not GOOGLE_API_KEY or len(GOOGLE_API_KEY) < 20: # 一個簡單的檢查，確認金鑰不是空的
        raise ValueError("GOOGLE_API_KEY 在 .env 檔案中為空或格式不正確。")
    print("✅ 步驟 2/4: 成功從 `.env` 檔案載入 `GOOGLE_API_KEY`。")
except Exception as e:
    print(f"❌ 錯誤：無法從 `.env` 檔案中讀取 `GOOGLE_API_KEY`。")
    print(f"   詳細錯誤: {e}")
    print("   請檢查您的 `.env` 檔案是否存在於專案根目錄，並且 `util/config.py` 的 Pydantic 模型定義正確。")
    sys.exit(1)

# --- 步驟 3: 設定 Google AI 服務 ---
import google.generativeai as genai
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("✅ 步驟 3/4: 成功使用載入的金鑰設定 Google AI 服務。")
except Exception as e:
    print(f"❌ 錯誤：`genai.configure` 失敗。")
    print(f"   詳細錯誤: {e}")
    sys.exit(1)

# --- 步驟 4: 實際呼叫 API 進行最終驗證 ---
try:
    print("\n--- 正在向 Google 查詢您帳號可用的模型列表 ---")
    found_model = False
    model_list = []
    for m in genai.list_models():
      if 'generateContent' in m.supported_generation_methods:
        model_list.append(f"- {m.name}")
        found_model = True
    
    if not found_model:
        print("\n⚠️  警告：雖然連線成功，但找不到任何支援 `generateContent` 的模型。")
        print("   請前往 Google Cloud Console，確認您的專案已啟用 'Vertex AI API'。")
    else:
        print("\n".join(model_list))
        print("\n✅ 步驟 4/4: API 金鑰有效！成功從 Google 獲取模型列表。")
        print("\n🎉 恭喜！您的環境配置完全正確，可以正常執行所有 AI 相關的腳本了！")

except Exception as e:
    print("\n❌ 錯誤：API 金鑰無效或 GCP 專案設定有問題！")
    print(f"   在嘗試呼叫 Google API 時發生錯誤: {type(e).__name__}")
    print(f"   詳細錯誤訊息: {e}")
    print("\n--- 除錯建議 ---")
    print("   1. 請再次確認您 `.env` 檔案中的 `GOOGLE_API_KEY` 是來自正確 GCP 專案的有效金鑰。")
    print("   2. 請確認您的 Google Cloud 專案已經啟用了 'Vertex AI API'。")
    print("   3. 請確認您的電腦網路連線正常，並且防火牆沒有阻擋對 Google 服務的訪問。")

print("\n=====================================")
print("健康檢查完畢。")
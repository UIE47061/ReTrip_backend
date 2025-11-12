from dotenv import load_dotenv, find_dotenv
import os

# 自動尋找專案根目錄的 .env
load_dotenv(find_dotenv(), override=False)

# 統一管理環境變數
class Env:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_SEARCH_ENGINE_ID: str = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "")
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    RELOAD: bool = os.getenv("RELOAD", "").lower() == "true"
    PORT: int = int(os.getenv("PORT", 7860))    # Hugging Face Spaces 預設使用 7860 port

env = Env()
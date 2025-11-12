# tools/test_google_and_insert.py

import sys
from pathlib import Path
# 确保可以从根目录导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import google.generativeai as genai
from util.config import env
from functions.supabaseFunction import google_search_for_attraction # 导入我们已有的 Google 搜索工具

# --- 初始化 ---
from supabase import create_client, Client
supabase: Client = create_client(env.SUPABASE_URL, env.SUPABASE_KEY)

genai.configure(api_key=env.GOOGLE_API_KEY)


async def test_single_attraction_creation(name: str):
    """
    一个专门的测试函式，用于测试单个景点的创建流程。
    """
    print(f"--- 任务开始：为「{name}」创建数据库记录 ---")

    # 步骤 1: 检查景點是否已存在
    print(f"\n1. 正在数据库中检查「{name}」是否存在...")
    search_response = await asyncio.to_thread(
        supabase.table('attractions').select('id, name').ilike('name', f'%{name}%').execute
    )
    if search_response.data:
        print(f"✅ 成功：景點「{search_response.data[0]['name']}」已存在于数据库中。")
        print(f"   ID: {search_response.data[0]['id']}")
        return

    print("   -> 景點不存在，继续创建流程。")

    # 步骤 2: 使用 Google 搜索获取信息
    print(f"\n2. 正在使用 Google 搜索「{name}」的资讯...")
    search_results = google_search_for_attraction(f"{name} 景點介紹 官方網站")
    if not search_results:
        print(f"❌ 失败：网络搜索也找不到 '{name}' 的信息。")
        return

    print("✅ 成功：已从 Google 找到相关资讯。")

    # 步骤 3: 让 Gemini 总结描述
    print(f"\n3. 正在请求 Gemini 总结描述...")
    summary_prompt = f"请根据以下的 Google 搜索结果，为景点「{name}」生成一段简洁、吸引人的繁体中文描述文字。"
    try:
        summary_response = await genai.GenerativeModel('gemini-pro-latest').generate_content_async(summary_prompt)
        new_description = summary_response.text
        print("✅ 成功：Gemini 已生成描述。")
    except Exception as e:
        print(f"❌ 失败：Gemini 生成描述时出错: {e}")
        return

    # 步骤 4: 将新景點写入数据库
    print(f"\n4. 正在将新景點「{name}」写入 Supabase 数据库...")
    try:
        # 我们只提供 name 和 description，id 应该由数据库自动生成
        insert_data = {"name": name, "description": new_description}
        insert_response = await asyncio.to_thread(
            supabase.table('attractions').insert(insert_data).execute
        )

        if insert_response.data:
            print("✅ 成功：资料已成功写入数据库！")
            print(f"   新景點的资料: {insert_response.data[0]}")
        else:
            print("❌ 失败：写入数据库时未收到回传资料。")
            print(f"   Supabase 回应: {insert_response}")

    except Exception as e:
        print(f"❌ 失败：写入数据库时发生严重错误: {e}")

    print("\n--- 任务结束 ---")


if __name__ == "__main__":
    # 我们要测试的目标景點
    target_attraction = "高雄85大樓"
    
    # 因为我们的函式是 async 的，所以需要用 asyncio.run() 来执行
    asyncio.run(test_single_attraction_creation(target_attraction))
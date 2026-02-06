import getpass
import json
import math
import sys
import time
from typing import List

try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False

TIMEOUT = 30

# Cloudflare Workers AI 支持的模型列表
CLOUDFLARE_MODELS = [
    "@cf/meta/llama-2-7b-chat-fp16",
    "@cf/meta/llama-2-7b-chat-int8",
    "@cf/meta/llama-3-8b-instruct",
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3.2-1b-instruct",
    "@cf/meta/llama-3.2-3b-instruct",
    "@cf/mistral/mistral-7b-instruct-v0.1",
    "@cf/mistral/mistral-7b-instruct-v0.2",
    "@hf/thebloke/deepseek-coder-6.7b-base-awq",
    "@hf/thebloke/deepseek-coder-6.7b-instruct-awq",
    "@cf/deepseek-ai/deepseek-math-7b-instruct",
    "@cf/openchat/openchat-3.5-0106",
    "@cf/google/gemma-2b-it-lora",
    "@cf/google/gemma-7b-it-lora",
    "@hf/nousresearch/hermes-2-pro-mistral-7b",
    "@hf/thebloke/llamaguard-7b-awq",
    "@cf/tinyllama/tinyllama-1.1b-chat-v1.0",
    "@cf/qwen/qwen1.5-0.5b-chat",
    "@cf/qwen/qwen1.5-1.8b-chat",
    "@cf/qwen/qwen1.5-7b-chat-awq",
    "@cf/qwen/qwen1.5-14b-chat-awq",
    "@cf/defog/sqlcoder-7b-2",
    "@cf/phi/phi-2",
]

# Cerebras 支持的模型列表
CEREBRAS_MODELS = [
    "llama3.1-8b",
    "llama3.1-70b",
    "llama-3.3-70b",
]

def is_cloudflare_api(url: str) -> bool:
    """检测是否为 Cloudflare Workers AI API"""
    return "cloudflare.com" in url.lower() and "/ai" in url.lower()

def is_cerebras_api(url: str) -> bool:
    """检测是否为 Cerebras API"""
    return "cerebras.ai" in url.lower()

def normalize_base_url(url: str) -> str:
    url = url.rstrip("/")
    # Cerebras 和其他已经包含 /v1 的不需要补全
    if not url.endswith("/v1"):
        if not is_cerebras_api(url):  # Cerebras URL 通常已包含 /v1
            print("[INFO] Base URL 未以 /v1 结尾，已自动补全")
            url += "/v1"
    return url

def build_headers(api_key: str, url: str = "") -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # 为不同的 API 定制 User-Agent
    if is_cerebras_api(url):
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    else:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    return headers

def safe_json(resp):
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON解析失败: {e}")
        return None
    except Exception as e:
        print(f"[WARN] 解析响应时出错: {e}")
        return None

def do_request(method: str, url: str, headers: dict, json_data: dict = None):
    try:
        # 为不同 API 选择最佳的浏览器模拟
        impersonate_version = "chrome131" if is_cerebras_api(url) else "chrome120"
        
        if HAS_CURL_CFFI:
            if method.upper() == "GET":
                return requests.get(url, headers=headers, timeout=TIMEOUT, impersonate=impersonate_version)
            else:
                return requests.post(url, headers=headers, json=json_data, timeout=TIMEOUT, impersonate=impersonate_version)
        else:
            if method.upper() == "GET":
                return requests.get(url, headers=headers, timeout=TIMEOUT)
            else:
                return requests.post(url, headers=headers, json=json_data, timeout=TIMEOUT)
    except Exception as e:
        print(f"[ERROR] 网络请求异常: {e}")
        return None

def fetch_models(base_url: str, headers: dict) -> List[str]:
    # 特殊处理 Cloudflare API
    if is_cloudflare_api(base_url):
        print("[INFO] 检测到 Cloudflare Workers AI API，使用内置模型列表")
        return CLOUDFLARE_MODELS
    
    # 特殊处理 Cerebras API
    if is_cerebras_api(base_url):
        print("[INFO] 检测到 Cerebras API，使用内置模型列表")
        return CEREBRAS_MODELS
    
    url = f"{base_url}/models"
    resp = do_request("GET", url, headers)

    if not resp: return []

    if resp.status_code == 405:
        print("[WARN] 该接口不支持获取模型列表 (HTTP 405 - Method Not Allowed)")
        return []

    if resp.status_code == 403:
        print("[WARN] 请求被防火墙拦截 (HTTP 403)")
        if not HAS_CURL_CFFI:
            print("       >> 建议安装 pip install curl_cffi 以绕过拦截")
        return []

    if resp.status_code != 200:
        print(f"[WARN] 模型列表获取失败 (HTTP {resp.status_code})")
        return []

    data = safe_json(resp)
    if not data:
        print("[WARN] /models 返回非 JSON 数据")
        return []

    raw = data.get("data")
    if not isinstance(raw, list):
        print("[WARN] /models 响应格式异常 (data不是列表)")
        return []

    models = []
    for m in raw:
        if isinstance(m, dict):
            model_id = m.get("id") or m.get("name")
            if model_id:
                models.append(model_id)

    return sorted(models)

def validate_inputs(base_url: str, api_key: str) -> bool:
    """验证用户输入的有效性"""
    if not api_key:
        print("[ERROR] API Key 不能为空")
        return False
    
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        print("[ERROR] URL 必须以 http:// 或 https:// 开头")
        return False
    
    return True

def choose_model(models: List[str]) -> str:
    if not models: return ""
    if len(models) == 1: return models[0]

    page_size = 15
    filtered_models = models
    page = 0

    while True:
        total = len(filtered_models)
        if total == 0:
            print("[WARN] 没有匹配的模型，重置搜索...")
            filtered_models = models
            total = len(filtered_models)
            page = 0

        start = page * page_size
        end = min(start + page_size, total)

        print("\n" + "-" * 50)
        if filtered_models != models:
            print(f" 🔍 搜索结果 ({page+1}/{math.ceil(total/page_size)}) - 共 {total} 个")
        else:
            print(f" 📖 模型列表 ({page+1}/{math.ceil(total/page_size)}) - 共 {total} 个")
        print("-" * 50)

        for i in range(start, end):
            # 显示在filtered_models中的索引，但存储原始索引用于返回
            print(f"[{i}] {filtered_models[i]}")

        print("-" * 50)
        cmd = input("操作: [数字]选择 | n 下一页 | p 上一页 | s 搜索 | r 重置 | q 退出: ").strip().lower()

        if cmd == "q": 
            sys.exit(0)
        elif cmd == "n":
            if end < total: page += 1
            else: print(">> 已经是最后一页了")
        elif cmd == "p":
            if page > 0: page -= 1
            else: print(">> 已经是第一页了")
        elif cmd == "s":
            keyword = input("🔎 输入搜索关键词: ").strip()
            if keyword:
                filtered_models = [m for m in models if keyword.lower() in m.lower()]
                page = 0
                print(f"[OK] 找到 {len(filtered_models)} 个匹配项")
                if len(filtered_models) == 0:
                    print("[WARN] 没有匹配的模型")
            else:
                print("[INFO] 关键词为空，未执行搜索")
        elif cmd == "r":
            filtered_models = models
            page = 0
            print("[OK] 已重置搜索")
        elif cmd.isdigit():
            idx = int(cmd)
            if 0 <= idx < total:
                return filtered_models[idx]
            else:
                print("❌ 序号无效")
        else:
            print("❌ 指令无效")

def chat_test(base_url: str, headers: dict, model: str, custom_msg: str = None):
    url = f"{base_url}/chat/completions"
    test_msg = custom_msg or "你好，你是谁？"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_msg}],
        "temperature": 0.7
    }

    print(f"\n[STEP 2] 正在发送测试: {model} ...")
    print(f"[INFO] 测试消息: {test_msg}")
    
    start_time = time.time()
    resp = do_request("POST", url, headers, json_data=payload)
    elapsed = time.time() - start_time

    if not resp:
        print(f"⏱️ 请求超时或失败 (耗时: {elapsed:.2f}s)")
        return

    print(f"⏱️ 响应时间: {elapsed:.2f}s")

    if resp.status_code != 200:
        print(f"[ERROR] 请求失败 (HTTP {resp.status_code})")
        try:
            print(f"错误详情: {resp.text[:300]}")
        except:
            pass
        return

    data = safe_json(resp)
    if not data:
        print("[ERROR] 返回内容无法解析为 JSON")
        return

    try:
        reply = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        print("\n" + "=" * 50)
        print("🎉 测试成功！模型回复如下：")
        print("=" * 50)
        print(reply)
        print("=" * 50)
        if usage:
            print(f"📊 Token 使用: 输入={usage.get('prompt_tokens', 'N/A')} | "
                  f"输出={usage.get('completion_tokens', 'N/A')} | "
                  f"总计={usage.get('total_tokens', 'N/A')}")
        print()
    except (KeyError, IndexError, TypeError) as e:
        print(f"[ERROR] 响应结构不符合 OpenAI 标准: {e}")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

def main():
    print("=" * 60)
    print(" OpenAI 兼容接口全能探测工具 V3.0")
    if HAS_CURL_CFFI:
        print(" [状态] ✅ 已启用 curl_cffi (防火墙穿透模式)")
    else:
        print(" [状态] ⚠️ 未检测到 curl_cffi，使用普通 requests (易被拦截)")
        print("        (推荐运行 pip install curl_cffi 以获得最佳效果)")
    print("=" * 60)

    base_url_in = input("API Base URL: ").strip()
    if not base_url_in:
        print("[ERROR] URL 不能为空")
        return
    
    base_url = normalize_base_url(base_url_in)
    api_key = getpass.getpass("API Key (输入时不显示): ").strip()

    if not validate_inputs(base_url, api_key):
        return

    headers = build_headers(api_key, base_url)

    print("\n[STEP 1] 探测模型列表...")
    models = fetch_models(base_url, headers)

    if not models:
        print("\n[INFO] 未能自动获取列表 (可能是接口不支持或被拦截)")
        manual_model = input("请输入模型 ID 手动测试 (例如 @cf/meta/llama-3-8b-instruct): ").strip()
        if not manual_model:
            print("未输入模型 ID，程序退出。")
            return
        model = manual_model
    else:
        print(f"[OK] 成功获取 {len(models)} 个模型")
        model = choose_model(models)

    # 询问是否使用自定义测试消息
    use_custom = input("\n是否使用自定义测试消息? (y/N): ").strip().lower()
    custom_msg = None
    if use_custom == 'y':
        custom_msg = input("请输入测试消息: ").strip()
        if not custom_msg:
            print("[INFO] 消息为空，使用默认测试消息")
            custom_msg = None

    chat_test(base_url, headers, model, custom_msg)

if __name__ == "__main__":
    main()
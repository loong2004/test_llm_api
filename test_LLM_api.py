import getpass
import json
import math
import sys
import time
from typing import List, Optional

try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests  # type: ignore
    HAS_CURL_CFFI = False

TIMEOUT = 30

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

CEREBRAS_MODELS = [
    "llama3.1-8b",
    "llama3.1-70b",
    "llama-3.3-70b",
]


def is_cloudflare_api(url: str) -> bool:
    return "cloudflare.com" in url.lower() and "/ai" in url.lower()


def is_cerebras_api(url: str) -> bool:
    return "cerebras.ai" in url.lower()


def normalize_base_url(url: str) -> str:
    url = url.rstrip("/")

    if url.endswith("/chat/completions"):
        return url

    if not url.endswith("/v1"):
        if is_cloudflare_api(url):
            print("[INFO] 检测到 Cloudflare Workers AI，自动补全 /v1（OpenAI 兼容端点）")
            url += "/v1"
        elif not is_cerebras_api(url):
            print("[INFO] Base URL 未以 /v1 结尾，已自动补全")
            url += "/v1"
        else:
            pass

    return url


def build_headers(api_key: str, url: str = "") -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 【关键修改】
    # 移除了手动设置 User-Agent 的代码。
    # 让 curl_cffi 的 impersonate 参数全权负责生成匹配的 User-Agent 和 TLS 指纹。
    # 这样可以避免因 Header 与 TLS 指纹不符导致的 Cloudflare 403 拦截。

    return headers


def safe_json(resp):
    try:
        return resp.json()
    except Exception as e:
        print(f"[WARN] JSON解析失败: {e}")
        try:
            print(f"[WARN] 响应内容预览(前500字): {resp.text[:500]}")
        except Exception:
            pass
        return None


def looks_like_cloudflare_challenge(resp) -> bool:
    try:
        ctype = (resp.headers.get("content-type") or "").lower()
    except Exception:
        ctype = ""
    try:
        text = (resp.text or "")[:2000].lower()
    except Exception:
        text = ""
    if "text/html" in ctype and ("attention required" in text or "cloudflare" in text):
        return True
    return False


def do_request(method: str, url: str, headers: dict, json_data: dict = None):
    try:
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
    if is_cloudflare_api(base_url):
        print("[INFO] 检测到 Cloudflare Workers AI API，使用内置模型列表")
        return CLOUDFLARE_MODELS

    if is_cerebras_api(base_url):
        print("[INFO] 检测到 Cerebras API，使用内置模型列表")
        return CEREBRAS_MODELS

    url = f"{base_url}/models"
    resp = do_request("GET", url, headers)

    if not resp:
        return []

    if resp.status_code == 405:
        print("[WARN] 该接口不支持获取模型列表 (HTTP 405 - Method Not Allowed)")
        return []

    if resp.status_code == 403:
        print("[WARN] 请求被拦截 (HTTP 403)")
        if looks_like_cloudflare_challenge(resp):
            print("[HINT] 看起来是 Cloudflare/WAF 挑战页（HTML），请求未到达 API。建议换网络/节点或稍后再试。")
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
    if not api_key:
        print("[ERROR] API Key 不能为空")
        return False
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        print("[ERROR] URL 必须以 http:// 或 https:// 开头")
        return False
    return True


def choose_model(models: List[str]) -> str:
    if not models:
        return ""
    if len(models) == 1:
        return models[0]

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
            print(f" 搜索结果 ({page+1}/{math.ceil(total/page_size)}) - 共 {total} 个")
        else:
            print(f" 模型列表 ({page+1}/{math.ceil(total/page_size)}) - 共 {total} 个")
        print("-" * 50)

        for i in range(start, end):
            print(f"[{i}] {filtered_models[i]}")

        print("-" * 50)
        cmd = input("操作: [数字]选择 | n 下一页 | p 上一页 | s 搜索 | r 重置 | q 退出: ").strip().lower()

        if cmd == "q":
            sys.exit(0)
        elif cmd == "n":
            if end < total:
                page += 1
            else:
                print(">> 已经是最后一页了")
        elif cmd == "p":
            if page > 0:
                page -= 1
            else:
                print(">> 已经是第一页了")
        elif cmd == "s":
            keyword = input("输入搜索关键词: ").strip()
            if keyword:
                filtered_models = [m for m in models if keyword.lower() in m.lower()]
                page = 0
                print(f"[OK] 找到 {len(filtered_models)} 个匹配项")
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
            print("❌ 序号无效")
        else:
            print("❌ 指令无效")


def chat_test(base_url: str, headers: dict, model: str, custom_msg: Optional[str] = None):
    # 如果用户输入了完整 endpoint，直接用；否则按 base_url 拼接
    if base_url.endswith("/chat/completions"):
        url = base_url
    else:
        url = f"{base_url}/chat/completions"

    test_msg = custom_msg or "你好，你是谁？"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": test_msg}],
        "temperature": 0.7,
    }

    print(f"\n[STEP 2] 正在发送测试: {model} ...")
    print(f"[INFO] Endpoint: {url}")
    print(f"[INFO] 测试消息: {test_msg}")

    start_time = time.time()
    resp = do_request("POST", url, headers, json_data=payload)
    elapsed = time.time() - start_time

    if not resp:
        print(f"[ERROR] 请求超时或失败 (耗时: {elapsed:.2f}s)")
        return

    print(f"[INFO] 响应时间: {elapsed:.2f}s")

    if resp.status_code != 200:
        print(f"[ERROR] 请求失败 (HTTP {resp.status_code})")
        try:
            if looks_like_cloudflare_challenge(resp):
                print("[HINT] 返回了 Cloudflare/WAF 挑战页（HTML），不是 API JSON 错误。建议换网络/节点或稍后再试。")
            print(f"错误详情预览: {resp.text[:500]}")
        except Exception:
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
        print("测试成功！模型回复如下：")
        print("=" * 50)
        print(reply)
        print("=" * 50)
        if usage:
            print(
                f"Token 使用: 输入={usage.get('prompt_tokens', 'N/A')} | "
                f"输出={usage.get('completion_tokens', 'N/A')} | "
                f"总计={usage.get('total_tokens', 'N/A')}"
            )
        print()
    except (KeyError, IndexError, TypeError) as e:
        print(f"[ERROR] 响应结构不符合 OpenAI 标准: {e}")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:800])


def main():
    print("=" * 60)
    print(" OpenAI 兼容接口全能探测工具 (Cerebras稳定版 + CF修正)")
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
        manual_model = input("请输入模型 ID 手动测试: ").strip()
        if not manual_model:
            print("未输入模型 ID，程序退出。")
            return
        model = manual_model
    else:
        print(f"[OK] 成功获取 {len(models)} 个模型")
        model = choose_model(models)

    use_custom = input("\n是否使用自定义测试消息? (y/N): ").strip().lower()
    custom_msg = None
    if use_custom == "y":
        custom_msg = input("请输入测试消息: ").strip() or None

    chat_test(base_url, headers, model, custom_msg)


if __name__ == "__main__":
    main()
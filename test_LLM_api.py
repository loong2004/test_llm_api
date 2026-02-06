import json
import math
import sys
from typing import List

# -----------------------------------------------------------------------------
# [核心升级] 尝试导入 curl_cffi 以通过 Cloudflare/Cerebras 的高强度验证
# -----------------------------------------------------------------------------
try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False

TIMEOUT = 30

def normalize_base_url(url: str) -> str:
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        print("[INFO] Base URL 未以 /v1 结尾，已自动补全")
        url += "/v1"
    return url

def build_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        # [关键修改] 伪装成真实的 Chrome 浏览器，防止被简单防火墙拦截
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

# [新增] 统一请求封装，自动处理指纹模拟
def do_request(method: str, url: str, headers: dict, json_data: dict = None):
    try:
        if HAS_CURL_CFFI:
            # impersonate="chrome110" 是穿透 Cloudflare 5秒盾的关键
            if method.upper() == "GET":
                return requests.get(url, headers=headers, timeout=TIMEOUT, impersonate="chrome110")
            else:
                return requests.post(url, headers=headers, json=json_data, timeout=TIMEOUT, impersonate="chrome110")
        else:
            # 回退到普通 requests
            if method.upper() == "GET":
                return requests.get(url, headers=headers, timeout=TIMEOUT)
            else:
                return requests.post(url, headers=headers, json=json_data, timeout=TIMEOUT)
    except Exception as e:
        print(f"[ERROR] 网络请求异常: {e}")
        return None

def fetch_models(base_url: str, headers: dict) -> List[str]:
    url = f"{base_url}/models"
    resp = do_request("GET", url, headers)

    if not resp: return []

    # 针对 Cloudflare 的特殊处理
    if resp.status_code == 405:
        print("[WARN] 该接口不支持获取模型列表 (HTTP 405 - Method Not Allowed)")
        return []
    
    # 针对 Cerebras 被拦截的处理
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
            # 兼容不同厂商的字段名 (id 或 name)
            model_id = m.get("id") or m.get("name")
            if model_id:
                models.append(model_id)

    return sorted(models) # 排序让列表更易读

def choose_model(models: List[str]) -> str:
    if not models: return ""
    if len(models) == 1: return models[0]

    page_size = 15 # 一页显示15个
    total = len(models)
    page = 0

    while True:
        start = page * page_size
        end = min(start + page_size, total)

        print("\n" + "-" * 50)
        print(f" 📖 模型列表 ({page+1}/{math.ceil(total/page_size)}) - 共 {total} 个")
        print("-" * 50)

        for i in range(start, end):
            print(f"[{i}] {models[i]}")

        print("-" * 50)
        cmd = input("操作: [数字]选择 | n 下一页 | p 上一页 | q 退出: ").strip().lower()

        if cmd == "q": sys.exit(0)
        elif cmd == "n":
            if end < total: page += 1
            else: print(">> 已经是最后一页了")
        elif cmd == "p":
            if page > 0: page -= 1
            else: print(">> 已经是第一页了")
        elif cmd.isdigit():
            idx = int(cmd)
            if 0 <= idx < total:
                return models[idx]
            else:
                print("❌ 序号无效")
        else:
            print("❌ 指令无效")

def chat_test(base_url: str, headers: dict, model: str):
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "你好，你是谁？"}],
        "temperature": 0.7
    }

    print(f"\n[STEP 2] 正在发送测试: {model} ...")
    resp = do_request("POST", url, headers, json_data=payload)

    if not resp: return

    if resp.status_code != 200:
        print(f"[ERROR] 请求失败 (HTTP {resp.status_code})")
        # 打印详细错误信息，方便调试
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
        print("\n" + "=" * 50)
        print("🎉 测试成功！模型回复如下：")
        print("=" * 50)
        print(reply)
        print("=" * 50 + "\n")
    except Exception:
        print("[ERROR] 响应结构不符合 OpenAI 标准")
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

    # 允许用户直接回车跳过输入（如果只是想快速测试硬编码的地址，可在代码里改）
    base_url_in = input("API Base URL: ").strip()
    if not base_url_in:
        print("错误: URL 不能为空")
        return
    
    base_url = normalize_base_url(base_url_in)
    api_key = input("API Key: ").strip()

    headers = build_headers(api_key)

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

    chat_test(base_url, headers, model)

if __name__ == "__main__":
    main()
import requests
import sys

def get_models(base_url, api_key):
    url = f"{base_url.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # 伪装成正常浏览器，降低被 Cloudflare 等 WAF 拦截的概率
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("\n正在尝试获取模型列表...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data:
            models = [model["id"] for model in data["data"]]
            return models, "SUCCESS", ""
        else:
            return [], "PARSE_ERROR", f"无法解析返回的 JSON: {data}"
            
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status in (401, 403):
            return [], "AUTH_ERROR", f"HTTP {status} 拒绝访问。API Key 错误、余额不足，或 IP 被防火墙(如Cloudflare)拦截。"
        elif status in (404, 405):
            return [], "UNSUPPORTED", f"HTTP {status}。该接口似乎没有实现标准的大模型列表路由。"
        else:
            return [], "HTTP_ERROR", f"HTTP {status} 请求失败。"
    except requests.exceptions.RequestException as e:
        return [], "NETWORK_ERROR", f"网络连接异常: {e}"

def test_chat_completion(base_url, api_key, model_name):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "你好！这是一条API测试消息。如果收到请回复“API连接成功！并介绍你是谁？”。"}
        ],
        "max_tokens": 100
    }
    
    print(f"\n正在向模型 [{model_name}] 发送测试消息 (最长等待60秒)...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        reply = result["choices"][0]["message"]["content"]
        print("\n测试成功！模型回复如下：")
        print("-" * 50)
        print(reply)
        print("-" * 50)
        
    except requests.exceptions.ReadTimeout:
        print(f"\n测试失败: 响应超时 (Read timed out)。")
    except Exception as e:
        print(f"\n测试失败，错误信息: {e}")
        # 如果是 HTML 页面（比如 Cloudflare 拦截页），就截取前 200 个字符，防止刷屏
        if 'response' in locals() and response.text:
            err_text = response.text.strip()
            if err_text.startswith("<!DOCTYPE html>") or err_text.startswith("<html"):
                print(f"接口返回了一个网页(大概率是被防火墙拦截了)，页面前段内容: {err_text[:200]}...")
            else:
                print(f"接口返回的详细错误: {err_text}")

def main():
    print("=" * 50)
    print("LLM API 可用性测试工具")
    print("=" * 50)
    
    while True:
        print("\n" + "-" * 20 + " 配置提供商 " + "-" * 20)
        base_url = input("请输入 API Base URL (例如 https://api.openai.com/v1): ").strip()
        api_key = input("请输入 API Key (sk-...): ").strip()
        
        if not base_url or not api_key:
            print("错误：URL 和 API Key 不能为空，请重新输入。")
            continue
            
        models, status, err_msg = get_models(base_url, api_key)
        
        # 核心逻辑修复点：根据状态码决定走向
        if status == "SUCCESS":
            print("\n成功获取到模型列表。")
            for idx, model in enumerate(models, 1):
                print(f"  {idx}. {model}")
            print(f"\n当前共支持 {len(models)} 个模型。")
            
        elif status == "UNSUPPORTED":
            print(f"提示：{err_msg}")
            print("进入手动模式。由于无法拉取列表，你需要明确知道你想测试的模型名称。")
            
        else:
            print(f"\n错误：获取模型列表失败 -> {err_msg}")
            retry = input("是否重新输入 Base URL 和 API Key？(y/n): ").strip().lower()
            if retry == 'y':
                continue
            else:
                print("脚本已退出。")
                sys.exit(0)
        
        while True:
            if status == "SUCCESS":
                choice = input(f"\n请输入模型序号 (1-{len(models)})，全名，或输入关键词搜索: ").strip()
                
                if not choice:
                    continue

                selected_model = None
                
                if choice in models:
                    selected_model = choice
                elif choice.isdigit():
                    choice_idx = int(choice)
                    if 1 <= choice_idx <= len(models):
                        selected_model = models[choice_idx - 1]
                    else:
                        print("错误：输入的序号超出范围，请重新输入。")
                        continue
                else:
                    keyword = choice.lower()
                    matches = [(idx + 1, m) for idx, m in enumerate(models) if keyword in m.lower()]
                    
                    if not matches:
                        print(f"未找到包含关键字 '{choice}' 的模型，请重新输入。")
                    else:
                        print(f"\n找到 {len(matches)} 个包含 '{choice}' 的模型：")
                        for orig_idx, m in matches:
                            print(f"  {orig_idx}. {m}")
                    continue
            else:
                # 列表为空时的手动模式
                choice = input("\n请输入你想测试的完整模型名称 (例如 @cf/meta/llama-3-8b-instruct): ").strip()
                if not choice:
                    continue
                selected_model = choice

            # 执行测试
            test_chat_completion(base_url, api_key, selected_model)
            
            print("\n" + "=" * 50)
            print("测试完成，请选择下一步操作：")
            print("  1. 测试该提供商的其他模型")
            print("  2. 更换 AI 提供商 (重新输入 URL 和 API Key)")
            print("  3. 退出脚本")
            print("=" * 50)
            
            next_step = input("请输入选项序号 (1/2/3): ").strip()
            
            if next_step == '1':
                continue 
            elif next_step == '2':
                break 
            elif next_step == '3':
                print("\n脚本已退出。")
                sys.exit(0)
            else:
                print("无效输入，默认返回重新测试模型。")
                continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n检测到强制中断，脚本已退出。")
        sys.exit(0)
import requests
import sys

def get_models(base_url, api_key):
    url = f"{base_url.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("\n正在获取模型列表，请稍候...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data:
            models = [model["id"] for model in data["data"]]
        else:
            print("警告：无法解析模型列表，原始返回：", data)
            return []
            
        return models
    except Exception as e:
        print(f"错误：获取模型列表失败: {e}")
        return []

def test_chat_completion(base_url, api_key, model_name):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "你好！这是一条API可用性测试消息。如果收到，请简要回复“API连接成功！”并介绍一下你自己。"}
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
        if 'response' in locals() and response.text:
            print(f"接口返回的详细错误: {response.text}")

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
            
        models = get_models(base_url, api_key)
        
        if not models:
            retry = input("是否重新输入 Base URL 和 API Key？(y/n): ").strip().lower()
            if retry == 'y':
                continue
            else:
                print("退出程序。")
                sys.exit(0)
                
        print("\n成功获取到模型列表。")
        for idx, model in enumerate(models, 1):
            print(f"  {idx}. {model}")
        print(f"\n当前共支持 {len(models)} 个模型。")
        
        while True:
            choice = input(f"\n请输入模型序号 (1-{len(models)})，全名，或输入关键词搜索: ").strip()
            
            if not choice:
                continue

            selected_model = None
            
            # 1. 匹配完整模型名称
            if choice in models:
                selected_model = choice
            # 2. 匹配纯数字序号
            elif choice.isdigit():
                choice_idx = int(choice)
                if 1 <= choice_idx <= len(models):
                    selected_model = models[choice_idx - 1]
                else:
                    print("错误：输入的序号超出范围，请重新输入。")
                    continue
            # 3. 执行模糊搜索
            else:
                keyword = choice.lower()
                # 记录匹配到的模型及其原本的序号
                matches = [(idx + 1, m) for idx, m in enumerate(models) if keyword in m.lower()]
                
                if not matches:
                    print(f"未找到包含关键字 '{choice}' 的模型，请重新输入。")
                else:
                    print(f"\n找到 {len(matches)} 个包含 '{choice}' 的模型：")
                    for orig_idx, m in matches:
                        print(f"  {orig_idx}. {m}")
                # 搜索完毕，回到输入提示处等待用户输入确切序号
                continue

            # 如果成功选定模型，执行测试
            test_chat_completion(base_url, api_key, selected_model)
            
            print("\n" + "=" * 50)
            print("测试完成，请选择下一步操作：")
            print("  1. 重新选择当前提供商的其他模型")
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
                print("无效输入，默认返回重新选择模型。")
                continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n检测到强制中断，脚本已退出。")
        sys.exit(0)
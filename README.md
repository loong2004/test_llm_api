# LLM API 可用性测试工具

一个功能强大的命令行工具，用于快速测试和验证各种大语言模型(LLM) API的可用性和连通性。

## 功能特性

✨ **核心功能：**
- 🔍 自动获取API提供商支持的模型列表
- 🧪 发送测试消息验证API连接
- 🛡️ 完善的异常处理和错误诊断
- 🔄 支持多提供商切换测试
- 🎯 灵活的模型选择方式（序号、全名、关键字搜索）

🚀 **用户体验优化：**
- 智能关键字搜索（单个匹配自动选中，多个匹配出菜单）
- 详细的错误信息和诊断建议
- 防火墙拦截检测（识别Cloudflare等WAF）
- 浏览器User-Agent伪装，降低被拦截概率
- 多轮次测试支持，无需重复配置

## 系统要求

- **Python**: 3.6+
- **依赖包**: `requests`

## 安装

### 1. 克隆或下载项目
```bash
cd your_project_directory
git clone https://github.com/loong2004/test_llm_api.git
```

### 2. 安装依赖
```bash
python -m pip install requests
```

## 快速开始

### 基本用法

```bash
python test.py
```

程序会提示你输入：
1. **API Base URL** - 例如：`https://api.openai.com/v1`
2. **API Key** - 例如：`sk-xxxxxxxxxxxxxx`

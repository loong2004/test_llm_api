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

### 使用示例

#### 示例 1: 测试 OpenAI API

```
请输入 API Base URL: https://api.openai.com/v1
请输入 API Key: sk-your-api-key-here

成功获取到模型列表。
  1. gpt-4-turbo
  2. gpt-4
  3. gpt-3.5-turbo
  ...

请输入模型序号 (1-3)，全名，或输入关键词搜索: gpt-4
已选择模型: gpt-4

正在向模型 [gpt-4] 发送测试消息 (最长等待60秒)...

测试成功！模型回复如下：
--------------------------------------------------
API连接成功！我是OpenAI开发的GPT-4模型...
--------------------------------------------------
```

#### 示例 2: 使用关键字搜索

```
请输入模型序号 (1-10)，全名，或输入关键词搜索: turbo

找到 2 个包含 'turbo' 的模型：
  3. gpt-3.5-turbo
  4. gpt-4-turbo-preview

请从上面的列表中选择模型序号: 3
已选择模型: gpt-3.5-turbo
```

#### 示例 3: 直接输入模型全名

```
请输入模型序号 (1-10)，全名，或输入关键词搜索: gpt-3.5-turbo
已选择模型: gpt-3.5-turbo
```

## 模型选择方式

程序支持三种方式选择模型：

| 方式 | 示例 | 说明 |
|------|------|------|
| **序号** | `1` 或 `2` | 输入模型在列表中的序号 |
| **全名** | `gpt-4-turbo` | 输入完整的模型名称 |
| **关键词搜索** | `gpt-4` | 输入包含的关键字，支持自动匹配 |

## 支持的API提供商

该工具支持任何遵循OpenAI API标准的服务，包括但不限于：

- ✅ **OpenAI** - https://api.openai.com/v1
- ✅ **Azure OpenAI** - https://your-resource.openai.azure.com/v1
- ✅ **Anthropic** -（支持兼容的服务）
- ✅ **Cloudflare Workers AI** - https://api.cloudflare.com/v1
- ✅ **Together AI** - https://api.together.xyz/v1
- ✅ **其他兼容服务** - 任何支持OpenAI API格式的服务


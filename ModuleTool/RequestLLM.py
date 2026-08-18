import pprint
import time
import json
import ollama
import sys
import datetime
import requests, base64, io, math

tools = [
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "calculator",       # 工具名
    #         "description": "计算数学表达式",   # 工具描述
    #         "parameters": {
    #             "type": "object",
    #             "properties": {     # 参数列表
    #                 "expression": {     # 参数名称
    #                     "type": "string",   # 参数类型
    #                     "description": "数学表达式，例如 123*456+789"   # 参数描述
    #                 }
    #             },
    #             "required": ["expression"]      # 必须输入的参数
    #         }
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "review",       # 工具名
            "description": "对待审核项目进行审核敲定，使用前请确保符合要求",   # 工具描述
            "parameters": {
                "type": "object",
                "properties": {     # 参数列表
                    "tusk_id": {     # 参数名称
                        "type": "string",   # 参数类型
                        "description": "任务ID必须与任务表单完全对应，8位数字ID",   # 参数描述
                        "pattern": "^\\d{8}$"
                    },
                    "result": {     # 参数名称
                        "type": "integer",   # 参数类型
                        "description": "审核结果0表示拒绝，1表示通过，1位数字",   # 参数描述
                        "pattern": "^\\d{1}$"
                    },
                },
                "required": ["tusk_id"]      # 必须输入的参数
            }
        }
    }
]

# sk-e216a73ab18a42159974c84bc239f802
_api_key = 'sk-4ea2a171cf86448da973c8dc15d18182'

def _image_to_base64(img):
    if type(img) is str:
        with open(img, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    elif type(img) is bytes:
        return base64.b64encode(img).decode("utf-8")
    else:
        return io.BytesIO(img)

def cosine_similarity(vec1, vec2):
    """
    计算两个长度相等的数字列表的余弦相似度
    :param vec1: 第一个数字列表（向量）
    :param vec2: 第二个数字列表（向量）
    :return: 余弦相似度值（范围[-1, 1]）
    """
    # 检查两个向量长度是否相等
    if len(vec1) != len(vec2):
        raise ValueError("两个向量的长度必须相等")

    # 计算向量点积
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    # 计算vec1的模长（L2范数）
    norm1 = math.sqrt(sum(a ** 2 for a in vec1))
    # 计算vec2的模长
    norm2 = math.sqrt(sum(b ** 2 for b in vec2))

    # 处理模长为0的情况（避免除以0）
    if norm1 == 0 or norm2 == 0:
        return 0.0

    # 计算并返回余弦相似度
    return dot_product / (norm1 * norm2)

class OllamaLLM:
    def __init__(self, messages):
        self.messages = messages

    def list(self):
        result = ollama.list()
        return [model.model for model in result.models]

    def chat(self, question, model_name="qwen3:8b"):
        self.messages.append({"role": 'user', "content": question})
        response_generator = ollama.chat(model=model_name, stream=True, messages=self.messages, options={"temperature": 1.9})

        result_all = ''
        for response in response_generator:
            content = response.message.content
            if content:
                result_all += content
                yield content

        self.messages.append({"role": 'assistant', "content": result_all})

    def vision(self, img_list, model_name="qwen3-vl:4b"):
        client = ollama.Client()
        content = """详细描述一下图片。先定图片类型。如果是图表，重点关注标题，图例，趋势。如果是照片或其他图片，请重点关注风格，内容，细节描述。如果是多张图请按顺序逐个描述。"""
        image_base64_list = [_image_to_base64(img) for img in img_list]
        message = [{
            "role": "user",
            "content": content,
            "images": image_base64_list  # 传入Base64编码的图像
        }]
        responses = client.chat(
            # minicpm-v
            # gemma3:4b
            # qwen3-vl:4b
            # qwen3-vl:8b
            model=model_name,  # 多模态模型
            messages=message
        )

        content = responses.message.content
        return content

    def embedding(self,input_list, model='qwen3-embedding:4b'):
        batch = ollama.embed(
            model=model,
            input=input_list
        )
        return batch['embeddings']

class Deepseek:
    def __init__(self, messages, tools, api_key=""):
        self.api_key = api_key
        self.messages = self._sanitize_initial_messages(messages)
        self.tools = self._sanitize_tools(tools)
        self.model = "deepseek-reasoner"
        self.temperature = 0.3
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.api_key}"
        }

    def update_tools(self, new_tools):
        self.tools = self._sanitize_tools(new_tools)

    def _sanitize_initial_messages(self, messages):
        sanitized = []
        for msg in messages:
            clean_msg = {"role": msg["role"]}
            if msg["role"] == "assistant" and "content" not in msg:
                clean_msg["content"] = ""
            else:
                clean_msg["content"] = msg.get("content", "")
            if msg["role"] == "assistant" and "tool_calls" in msg:
                clean_msg["tool_calls"] = self._sanitize_tool_calls(msg["tool_calls"])
            if msg["role"] == "tool":
                required_fields = ["tool_call_id", "name", "content"]
                for field in required_fields:
                    if field not in msg:
                        raise ValueError(f"Tool message missing required field: {field}")
                clean_msg.update({
                    "tool_call_id": msg["tool_call_id"],
                    "name": msg["name"],
                    "content": msg["content"]
                })
            sanitized.append(clean_msg)
        return sanitized

    def _sanitize_tool_calls(self, tool_calls):
        sanitized = []
        for tool in tool_calls:
            sanitized_tool = {
                "id": tool.get("id", f"call_{int(time.time() * 1000)}"),
                "type": "function",
                "function": {
                    "name": tool["function"]["name"],
                    "arguments": json.dumps(tool["function"].get("arguments", {}))
                }
            }
            sanitized.append(sanitized_tool)
        return sanitized

    def _sanitize_tools(self, tools):
        if not tools:
            return []
        sanitized = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                sanitized.append({
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                        "strict": True
                    }
                })
        return sanitized

    def chat_stream(self, question, enable_web_search=False):
        if question:
            self.messages.append({"role": "user", "content": question})
        payload = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "stream": True
        }
        if self.tools:
            payload["tools"] = self.tools
        if enable_web_search:
            payload["enable_web_search"] = enable_web_search

        # print("="*10)
        # pprint.pprint(self.tools)
        # print("=" * 10)

        full_text = ""
        full_think = ""
        tool_cache = {}
        url = "https://api.deepseek.com/v1/chat/completions"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                stream=True,
                timeout=30
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue
                s = line.decode('utf-8').lstrip('data: ')
                if s == '[DONE]':
                    break

                chunk = json.loads(s)
                delta = chunk['choices'][0]['delta']

                text_chunk = delta.get('content', '') or ''
                full_text += text_chunk
                think_chunk = delta.get('reasoning_content', '') or ''
                full_think += think_chunk

                for tool in delta.get('tool_calls', []):
                    idx = tool.get('index', 0)
                    if idx not in tool_cache:
                        tool_cache[idx] = {
                            "id": tool.get('id', ''),
                            "name": tool['function'].get('name', ''),
                            "args": ""
                        }
                    tool_cache[idx]["args"] += tool['function'].get('arguments', '')

                yield None, text_chunk, think_chunk

            tools_list = []
            for item in tool_cache.values():
                try:
                    args = json.loads(item["args"])
                except json.JSONDecodeError:
                    args = {}
                tools_list.append({
                    "tool_call_id": item["id"],
                    "tool_name": item["name"],
                    "args": args
                })
            final_result = {
                "text": full_text,
                "think": full_think,
                "tools": tools_list
            }

            assistant_msg = {"role": "assistant", "content": full_text}
            if tools_list:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tool["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": tool["tool_name"],
                            "arguments": json.dumps(tool["args"])
                        }
                    } for tool in tools_list
                ]
            self.messages.append(assistant_msg)

            yield final_result, "", ""

        except requests.exceptions.RequestException as e:
            error_msg = f"API请求错误: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" 详细信息: {error_detail.get('error', {}).get('message', '')}"
                except:
                    pass
            yield {"text": "", "think": "", "error": error_msg}, "", ""

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str):
        self.messages.append({
            "role": "tool",
            "name": tool_name,
            "tool_call_id": tool_call_id,
            "content": str(result)
        })

def request_function(tools_dict, tool_call_id, tool_name, args):
    tool = tools_dict.get(tool_name)
    if tool:
        try:
            res = tool(**args)
        except Exception as e:
            res = f"<Error> 工具调用错误：{e}"
        return {'tool_call_id': tool_call_id, 'tool_name': tool_name, 'result': res}
    else:
        return {'tool_call_id': tool_call_id, 'tool_name': tool_name, 'result': f"<Error> 未知工具：{tool_name}"}

if __name__ == '__main__':
    YOUR_API_KEY = _api_key

    # 完整系统提示
    system_msg = [{"role": 'system', "content": '通过工具尝试完成用户需求，思考过程和对话使用中文。'}]

    # 完整工具定义
    audit_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "获取当前系统时间",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    ]

    # 初始化
    d = Deepseek(messages=system_msg, tools=audit_tools, api_key=YOUR_API_KEY)

    # 用户输入
    user_input = input('input:').strip()
    test_content = """现在几点了"""
    prompt = user_input if user_input else test_content

    final_result = None
    # 严格对应：result, text_chunk, think_chunk
    for result, text, think in d.chat_stream(prompt, thinking_mode=True):
        # UI 直接追加文本，不清空！
        print(text, end="", flush=True)
        # 存储最终结果
        if result is not None:
            final_result = result

    # 最终结果
    print(f"\n{final_result}")

    from RequestFunction import request_function

    for tool in final_result['tools']:
        result = request_function(**tool)

        d.add_tool_result(result)


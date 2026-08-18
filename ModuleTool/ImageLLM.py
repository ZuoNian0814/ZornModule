import base64
import mimetypes
from dashscope import MultiModalConversation
import dashscope
import requests
from pathlib import Path

api_key = "sk-75fdbd2a9e234984bc7f65ddf55297de"

def download_img(url: str, save_path: str | Path):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    Path(save_path).write_bytes(resp.content)

def encode_file(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("不支持或无法识别的图像格式")
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_string}"

def text_to_image(
        prompt,
        save_path,
        negative_prompt="低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。",
    ):
    # 以下为华北2（北京）地域的URL，各地域的URL不同。
    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'
    messages = [
        {
            "role": "user",
            "content": [
                {"text": prompt}
            ]
        }
    ]
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"

    response = MultiModalConversation.call(
        api_key=api_key,
        model="qwen-image-2.0-pro",
        messages=messages,
        result_format='message',
        stream=False,
        watermark=False,
        prompt_extend=True,
        negative_prompt=negative_prompt,
        size='640*640'
    )

    if response.status_code == 200:
        image_url = response["output"]["choices"][0]["message"]["content"][0]["image"]
        download_img(image_url, save_path)
        # print(json.dumps(response, ensure_ascii=False))
    else:
        print(f"HTTP返回码：{response.status_code}")
        print(f"错误码：{response.code}")
        print(f"错误信息：{response.message}")
        print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")

def image_to_image(
        prompt,
        image_path,
        save_path,
        negative_prompt="不自然，动作夸张，表情夸张，风格变化，画面噪声，低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。",
    ):
    # 【方式三】使用Base64编码的图片
    image_1 = encode_file(image_path)
    # image_2 = encode_file("/path/to/your/paint.png")

    # 以下为中国（北京）地域url，若使用新加坡地域的模型，需将url替换为：https://dashscope-intl.aliyuncs.com/api/v1
    dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

    # 模型支持输入1-3张图片
    messages = [
        {
            "role": "user",
            "content": [
                {"text": prompt},
                {"image": image_1}
            ]
        }
    ]

    # qwen-image-2.0系列、qwen-image-edit-max、qwen-image-edit-plus系列支持输出1-6张图片
    response = MultiModalConversation.call(
        api_key=api_key,
        model="qwen-image-2.0",  # qwen-image-2.0 / qwen-image-2.0-pro
        messages=messages,
        stream=False,
        n=1,
        watermark=False,
        negative_prompt=negative_prompt,
        prompt_extend=True,
        size="800*800",
    )

    if response.status_code == 200:
        # 如需查看完整响应，请取消下行注释
        # print(json.dumps(response, ensure_ascii=False))
        for i, content in enumerate(response.output.choices[0].message.content):
            # print(f"输出图像{i + 1}的URL:{content['image']}")
            download_img(content['image'], save_path)
    else:
        print(f"HTTP返回码：{response.status_code}")
        print(f"错误码：{response.code}")
        print(f"错误信息：{response.message}")
        print("请参考文档：https://help.aliyun.com/zh/model-studio/error-code")

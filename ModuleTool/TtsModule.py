# sk-75fdbd2a9e234984bc7f65ddf55297de
import os
import threading
import time
import wave
import requests
import dashscope
import soundcard as sc
import numpy as np

API_KEY = "sk-75fdbd2a9e234984bc7f65ddf55297de"  # 填入你的API Key
TTS_MODEL = "qwen3-tts-instruct-flash"
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
CHANNELS = 1
END_SILENCE_MS = 500

class QwenTTS:
    """极简版阿里云有声书TTS合成类（修复结尾截断+添加停顿）"""
    def __init__(self):
        dashscope.api_key = API_KEY
        if not dashscope.api_key:
            raise ValueError("请先填写有效的API Key！")
        self.model = TTS_MODEL

    def synthesize(self, text: str, voice: str, instructions: str, save_path: str = None, play: bool = True):
        threading.Thread(target=self._synthesize, args=(text, voice, instructions, save_path, play)).start()

    def _synthesize(self, text: str, voice: str, instructions: str, save_path: str = None, play: bool = True):
        if save_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            time_str = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
            save_path = os.path.join(script_dir, f"{time_str}.wav")

        try:
            print(f"正在合成音频：角色={voice}，文本={text[:20]}...")
            # 你的原始TTS调用（完全不动）
            resp = dashscope.MultiModalConversation.call(
                model=self.model,
                text=text,
                voice=voice,
                language_type="Chinese",
                instructions=instructions,
                optimize_instructions=True,
                stream=False
            )

            # 下载保存音频（完全不动）
            audio_url = resp.output.audio.url
            audio_data = requests.get(audio_url, timeout=60).content

            with wave.open(save_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)

            file_path = os.path.abspath(save_path)
            print(f"✅ 音频合成完成！保存路径：{file_path}")

            # ===================== 修复：结尾添加停顿，完整无截断播放 =====================
            if play:
                print("🔊 播放音频（结尾带停顿）...")
                with wave.open(file_path, 'rb') as wf:
                    frames = wf.readframes(wf.getnframes())
                    # 转换为标准格式
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

                # 生成结尾静音数据（无渐隐，纯停顿）
                silence_samples = int(SAMPLE_RATE * END_SILENCE_MS / 1000)
                silence_data = np.zeros(silence_samples, dtype=np.float32)

                # 拼接：原音频 + 结尾静音
                final_audio = np.concatenate([audio, silence_data])

                # 播放完整音频
                sc.default_speaker().play(final_audio, samplerate=SAMPLE_RATE)
            # ==============================================================================

            return file_path

        except Exception as e:
            error_msg = f"❌ 合成失败：{str(e)}"
            print(error_msg)
            return error_msg


# -------------------------- 使用示例（完全不变） --------------------------
if __name__ == "__main__":
    tts = QwenTTS()
    # Cherry 女
    # Serena 女
    # Ethan 男
    # Chelsie 女
    # Momo 女 萝莉
    # Vivian 女 拽姐
    # Moon 男
    # Maia 女
    # Kai 男
    # Nofish 男
    # Bella 女 萝莉
    # Mia 女
    # Mochi 男 正太
    # Bunny 女
    # Nini 女 萝莉
    # Seren 女 御姐
    # Stella 女
    tts.synthesize(
        text="那年的夏天格外漫长，蝉鸣从清晨到傍晚，从未停歇。",
        voice="Bella",
        instructions="语速中等偏快，活泼开朗，语气平稳"
    )
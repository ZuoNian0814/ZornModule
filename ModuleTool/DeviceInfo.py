import socket
import psutil
import requests
import platform
import subprocess
import re
from typing import Dict, Optional
from mss import mss

# import soundcard as sc

import numpy as np
import warnings
import time
import string
import os
from datetime import datetime
import shutil
import cv2
import threading
from PIL import Image

# warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)


class ScreenshotManager:
    def __init__(self):
        with mss() as temp_sct:
            self.monitors = temp_sct.monitors
        self.thread_local = threading.local()
        print(f"初始化完成，检测到 {self.get_monitor_count()} 个屏幕")

    def get_monitor_bounds(self, monitor_index: int):
        """
        获取指定索引屏幕的【Windows全局像素坐标范围】
        :param monitor_index: 屏幕索引（从0开始）
        :return: (x0, y0, x1, y1) 左上角坐标 + 右下角坐标
        """
        # 索引合法性校验（和截图方法保持一致）
        max_index = self.get_monitor_count() - 1
        if monitor_index < 0 or monitor_index > max_index:
            raise ValueError(f"显示器索引无效，有效范围 0 ~ {max_index}")

        # 获取原始屏幕参数（mss索引=用户索引+1）
        monitor = self.monitors[monitor_index + 1]
        x0 = monitor["left"]
        y0 = monitor["top"]
        x1 = x0 + monitor["width"]
        y1 = y0 + monitor["height"]

        return x0, y0, x1, y1

    def get_monitor_count(self) -> int:
        return len(self.monitors) - 1

    def _get_thread_sct(self):
        if not hasattr(self.thread_local, 'sct'):
            self.thread_local.sct = mss()
        return self.thread_local.sct

    def capture(self, monitor_index: int = 0, region: Optional[tuple] = None) -> Image.Image:
        if monitor_index < 0 or monitor_index >= self.get_monitor_count():
            raise ValueError(f"显示器索引无效，有效范围 0 到 {self.get_monitor_count() - 1}")

        sct = self._get_thread_sct()
        monitor = self.monitors[monitor_index + 1].copy()
        if monitor["width"] in [1707, 1280, 2048, 1463, 1138, 1024]:
            monitor["height"] = monitor["height"] * 2560 // monitor["width"]
            monitor["width"] = 2560
        elif monitor["width"] in [1536, 1280, 1097, 960, 853, 768]:
            monitor["height"] = monitor["height"] * 1920 // monitor["width"]
            monitor["width"] = 1920

        if region:
            left, top, width, height = region
            monitor["left"] += left
            monitor["top"] += top
            monitor["width"] = width
            monitor["height"] = height

        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        return img

    def close(self):
        if hasattr(self.thread_local, 'sct'):
            self.thread_local.sct.close()
            del self.thread_local.sct

class CameraManager:
    """管理摄像头资源的类，每个线程可选择独立打开摄像头句柄。"""
    def __init__(self):
        # 枚举索引 0..9 快速检查可用摄像头数量（DirectShow 仅在 Windows 上有效）
        camera_count = 0
        for index in range(10):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                camera_count += 1
                cap.release()
        self._camera_count = camera_count
        self.thread_local = threading.local()
        print(f"初始化完成，检测到 {self._camera_count} 个摄像头")

    def get_camera_count(self) -> int:
        """返回检测到的摄像头总数。"""
        return self._camera_count

    def _get_thread_capture(self, camera_index: int):
        """返回当前线程持有的 VideoCapture 对象（首次使用时创建并缓存）。"""
        if not hasattr(self.thread_local, 'captures'):
            self.thread_local.captures = {}
        captures = self.thread_local.captures
        if camera_index not in captures:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开摄像头 {camera_index}")
            captures[camera_index] = cap
        return captures[camera_index]

    def capture(self, camera_index: int = 0, mirror: bool = True) -> Image.Image:
        """
        从指定摄像头索引获取一帧画面，返回 PIL Image 对象（RGB 模式，无压缩）。
        :param camera_index: 摄像头索引（从0开始）
        :param mirror: 是否水平镜像画面，默认为 True
        :return: PIL Image 对象
        """
        if camera_index < 0 or camera_index >= self._camera_count:
            raise ValueError(f"摄像头索引无效，有效范围 0 到 {self._camera_count - 1}")
        cap = self._get_thread_capture(camera_index)
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError(f"从摄像头 {camera_index} 获取画面失败")
        if mirror:
            frame = cv2.flip(frame, 1)   # 水平镜像
        # OpenCV 默认 BGR 格式，转换为 RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_frame)

    def close(self):
        """关闭当前线程所有的摄像头句柄。多线程环境下需要每个线程分别调用。"""
        if hasattr(self.thread_local, 'captures'):
            for cap in self.thread_local.captures.values():
                cap.release()
            del self.thread_local.captures

# class VoiceManager:
#     def __init__(self, BLOCKSIZE=2048, SAMPLERATE=44100, VOLUME=1.0):
#         self.BLOCKSIZE = BLOCKSIZE
#         self.SAMPLERATE = SAMPLERATE
#
#         self.speaker = sc.default_speaker()
#         self.recorder_speakers = sc.get_microphone(id=self.speaker.id, include_loopback=True)
#         self.recorder_microphone = sc.default_microphone()
#
#         # 播放设备：默认扬声器（单独分离出来）
#         self.player_speaker = sc.default_speaker()
#
#         self.break_speakers = False
#         self.break_microphone = False
#
#     # 中断输出
#     def break_speakers(self):
#         self.break_speakers = True
#
#     def break_microphone(self):
#         self.break_microphone = True
#
#     def collect_speakers(self, seconds: float=1.0, info=False):
#         self.break_speakers = False
#         BLOCKSIZE = self.BLOCKSIZE
#         SAMPLERATE = self.SAMPLERATE
#         start = time.time()
#         loudness, dominant_freq = None, None
#         with self.recorder_speakers.recorder(samplerate=SAMPLERATE, channels=2, blocksize=BLOCKSIZE) as recorder:
#             while time.time() - start < seconds or seconds <= 0.0:
#                 if self.break_speakers:
#                     break
#                 # 声音信息
#                 audio_data = recorder.record(numframes=BLOCKSIZE)
#
#                 if info:
#                     mono_data = np.mean(audio_data, axis=1)
#                     # 计算响度
#                     rms = np.sqrt(np.mean(np.square(mono_data)))
#                     loudness = 20 * np.log10(max(rms, 1e-6))
#                     # 计算主频率
#                     fft_vals = np.fft.rfft(mono_data)
#                     freqs = np.fft.rfftfreq(len(mono_data), 1 / SAMPLERATE)
#                     dominant_freq = freqs[np.argmax(np.abs(fft_vals))]
#
#                 # # 实时打印
#                 # print(f"\r响度：{loudness:>6.1f} dB | 主频率：{dominant_freq:>7.1f} Hz", end="")
#                 yield audio_data, loudness, dominant_freq
#
#     def collect_microphone(self, seconds: float=1.0, info=False):
#         self.break_microphone = False
#         BLOCKSIZE = self.BLOCKSIZE
#         SAMPLERATE = self.SAMPLERATE
#         start = time.time()
#         loudness, dominant_freq = None, None
#         with self.recorder_microphone.recorder(samplerate=SAMPLERATE, channels=2, blocksize=BLOCKSIZE) as recorder:
#             while time.time() - start < seconds or seconds <= 0.0:
#                 if self.break_microphone:
#                     break
#                 # 声音信息
#                 audio_data = recorder.record(numframes=BLOCKSIZE)
#
#                 if info:
#                     mono_data = np.mean(audio_data, axis=1)
#                     # 计算响度
#                     rms = np.sqrt(np.mean(np.square(mono_data)))
#                     loudness = 20 * np.log10(max(rms, 1e-6))
#                     # 计算主频率
#                     fft_vals = np.fft.rfft(mono_data)
#                     freqs = np.fft.rfftfreq(len(mono_data), 1 / SAMPLERATE)
#                     dominant_freq = freqs[np.argmax(np.abs(fft_vals))]
#
#                 # # 实时打印
#                 # print(f"\r响度：{loudness:>6.1f} dB | 主频率：{dominant_freq:>7.1f} Hz", end="")
#                 yield audio_data, loudness, dominant_freq
#
#     def play_voice(self, audio_iterator, VOLUME=1.0):
#         SAMPLERATE = self.SAMPLERATE
#         with self.player_speaker.player(samplerate=SAMPLERATE, channels=2) as player:
#             for audio_data, loudness, dominant_freq in audio_iterator:
#                 player.play(audio_data * VOLUME)

class HostInfo:
    def __init__(self):
        # 全局超时配置（保证高效不卡顿）
        self.timeout = 2

    # ==================== 1. 获取主机名 ====================
    def get_hostname(self) -> Dict[str, str]:
        """获取主机名"""
        try:
            return {"主机名": socket.gethostname()}
        except Exception:
            return {"主机名": "未知"}

    # ==================== 2. 获取内网IP ====================
    def get_inner_ip(self) -> Dict[str, str]:
        def get_internal_ip():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(('10.255.255.255', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()
            return IP

        try:
            return {"真实内网IP": get_internal_ip()}
        except Exception:
            return {"真实内网IP": "未知"}

    # ==================== 3. 获取公网IP ====================
    def get_public_ip(self) -> Dict[str, str]:
        """获取公网IP地址（最快、最稳定的接口）"""
        try:
            resp = requests.get("https://api.ipify.org", timeout=self.timeout)
            resp.raise_for_status()
            return {"公网IP": resp.text.strip()}
        except Exception:
            try:
                # 发送GET请求，超时5秒，关闭重定向（部分API会跳转）
                response = requests.get("https://myip.ipip.net/", timeout=5, allow_redirects=True)
                # 提取IP并去除首尾空白（部分API返回带换行/空格）
                ip = response.text.split(' ')[1].split('：')[-1]
                return {"公网IP": ip}
            except:
                return {"公网IP": "未连接外网"}

    # ==================== 4. 获取CPU信息 ====================
    def get_cpu_info(self) -> Dict[str, Optional[str | int | float]]:
        """CPU：型号、核心总数、使用率"""
        try:
            return {
                "CPU型号": platform.processor(),
                "CPU核心数(物理)": psutil.cpu_count(logical=False) or 0,
                "CPU核心数(逻辑)": psutil.cpu_count(logical=True) or 0,
                "CPU使用率(%)": psutil.cpu_percent(interval=0.1)
            }
        except Exception:
            return {"CPU信息": "获取失败"}

    # ==================== 5. 获取GPU信息（仅NVIDIA，最稳定） ====================
    def get_gpu_info(self) -> Dict:
        """GPU：型号、总显存、已用显存（无NVIDIA则返回空）"""
        gpus = []
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                text=True, timeout=self.timeout
            )
            for line in output.strip().split("\n"):
                name, total, used = line.split(", ")
                gpus.append({
                    "GPU型号": name.strip(),
                    "总显存(MB)": int(total.strip()),
                    "已用显存(MB)": int(used.strip())
                })
            return {"GPU列表": gpus if gpus else "无独立显卡或未安装NVIDIA驱动"}
        except Exception:
            return {"GPU列表": "无独立显卡或未安装NVIDIA驱动"}

    # ==================== 6. 获取内存信息 ====================
    def get_memory_info(self) -> Dict[str, str | int]:
        """内存：类型、总容量、已用容量"""
        try:
            mem = psutil.virtual_memory()
            # 内存类型（极简跨平台获取，无则返回未知）
            mem_type = "未知"
            try:
                if platform.system() == "Windows":
                    mem_type = subprocess.check_output("wmic memorychip get devicelocator, memorytype", text=True,
                                                       timeout=1)
                elif platform.system() == "Linux":
                    mem_type = subprocess.check_output("sudo dmidecode -t memory | grep -m1 Type:", text=True,
                                                       timeout=1)
            except Exception:
                pass

            return {
                "内存类型": mem_type.strip() if isinstance(mem_type, str) else "未知",
                "总内存(GB)": round(mem.total / 1024 ** 3, 2),
                "已用内存(GB)": round(mem.used / 1024 ** 3, 2),
                "内存使用率(%)": mem.percent
            }
        except Exception:
            return {"内存信息": "获取失败"}

    # ==================== 7. 获取磁盘信息 ====================
    def get_disk_info(self) -> Dict:
        """磁盘：盘符、总容量、已用容量"""
        disks = []
        try:
            for part in psutil.disk_partitions(all=False):
                # 过滤系统保留分区
                if "fixed" in part.opts or platform.system() == "Linux":
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "盘符/挂载点": part.device,
                        "总容量(GB)": round(usage.total / 1024 ** 3, 2),
                        "已用容量(GB)": round(usage.used / 1024 ** 3, 2),
                        "使用率(%)": usage.percent
                    })
            return {"磁盘列表": disks}
        except Exception:
            return {"磁盘列表": "获取失败"}

    # ==================== 8. 获取网络/WiFi信息 ====================
    def get_wifi_info(self) -> Dict[str, str]:
        def get_wifi():
            system = platform.system()
            wifi_name = "未连接WiFi"

            if system == "Windows":
                output = subprocess.check_output("netsh wlan show interfaces", text=True, timeout=self.timeout)
                match = re.search(r"SSID\s+:\s(.+)", output)
                if match:
                    wifi_name = match.group(1).strip()

            elif system == "Linux":
                output = subprocess.check_output("iwgetid -r", text=True, timeout=self.timeout)
                wifi_name = output.strip() or "未连接WiFi"

            elif system == "Darwin":
                output = subprocess.check_output(
                    "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I | grep SSID",
                    shell=True, text=True, timeout=self.timeout
                )
                match = re.search(r"SSID:\s(.+)", output)
                if match:
                    wifi_name = match.group(1).strip()

            return decode_wifi_name(wifi_name), wifi_name

        def get_wifi_password() -> Dict[str, str]:
            """获取已连接WiFi的明文密码（仅Windows，仅支持已保存的WiFi）"""
            try:
                # 1. 获取当前WiFi名称
                wifi_name = get_wifi()[0]
                if wifi_name == "未连接WiFi或无无线网卡" or wifi_name == "未连接WiFi":
                    return {"状态": "未连接WiFi", "WiFi名称": "", "密码": ""}

                # 2. 调用系统命令获取密码
                output = subprocess.check_output(
                    f'netsh wlan show profile name="{wifi_name}" key=clear',
                    text=True, timeout=self.timeout
                )
                # 3. 正则提取密码
                pass_match = re.search(r"关键内容\s+:\s(.+)", output)
                password = pass_match.group(1).strip() if pass_match else "未保存密码"

                return {
                    "状态": "已连接",
                    "WiFi名称": wifi_name,
                    "WiFi密码": password
                }
            except Exception:
                return {"状态": "获取密码失败", "WiFi名称": "", "密码": ""}

        # 十六进制WiFi名称解码
        def decode_wifi_name(hex_name):
            """将UTF-8十六进制编码的WiFi名称解码为中文"""
            try:
                # 十六进制字符串转字节
                bytes_data = bytes.fromhex(hex_name)
                # 字节按UTF-8解码为中文
                return bytes_data.decode('utf-8')
            except Exception as e:
                return f"解码失败: {str(e)}"

        """获取当前连接的WiFi名称"""
        try:
            return {"当前WiFi名称": get_wifi(), "wifi密码": get_wifi_password()}
        except Exception:
            return {"当前WiFi名称": "未连接WiFi或无无线网卡"}

class DiskManager:
    def __init__(self):
        pass

    def get_disks(self):
        # 获取 A-Z 所有字母，拼接成盘符（C:\、D:\...）
        drives = []
        for c in string.ascii_uppercase:
            disk = c + ":\\"
            if os.path.exists(disk):  # 判断盘符是否存在
                drives.append(disk)
        return drives

    def get_dir_items(self, target_path):
        items = {"folder": [], 'file': []}
        for name in os.listdir(target_path):
            full_path = os.path.join(target_path, name)
            if os.path.isfile(full_path):
                items["file"].append(full_path)
            else:
                items["folder"].append(full_path)
        return items

    def get_item_time(self, path):
        return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")

    def get_file_size(self, path, num_mode=False):
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if num_mode:
                return size
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024:
                    return f"{size:.2f} {unit}"
                size /= 1024
        else:
            return ""


    def get_item_type(self, path):
        if os.path.isfile(path):
            return path.split(".")[-1].upper()
        else:
            return "Folder"

    def get_disk_usage(self, drive_path):
        """获取指定盘符的使用率（0到1的浮点数）"""
        usage = shutil.disk_usage(drive_path)
        return usage.used / usage.total  # 已用空间 / 总空间 = 使用率

if __name__ == '__main__':
    # # 初始化实例
    # host = HostInfo()
    # print("=" * 50)
    # print("主机信息测试（逐方法验证）")
    # print("=" * 50)
    #
    # # 1. 测试主机名
    # print("\n1. 主机名：")
    # pprint.pprint(host.get_hostname())
    #
    # # 2. 测试内网IP
    # print("\n2. 内网IP：")
    # pprint.pprint(host.get_inner_ip())
    #
    # # 3. 测试公网IP
    # print("\n3. 公网IP：")
    # pprint.pprint(host.get_public_ip())
    #
    # # 4. 测试CPU信息
    # print("\n4. CPU信息：")
    # pprint.pprint(host.get_cpu_info())
    #
    # # 5. 测试GPU信息
    # print("\n5. GPU信息：")
    # pprint.pprint(host.get_gpu_info())
    #
    # # 6. 测试内存信息
    # print("\n6. 内存信息：")
    # pprint.pprint(host.get_memory_info())
    #
    # # 7. 测试磁盘信息
    # print("\n7. 磁盘信息：")
    # pprint.pprint(host.get_disk_info())
    #
    # # 8. 测试WiFi信息
    # print("\n8. 网络信息：")
    # pprint.pprint(host.get_wifi_info())
    #
    # print("\n" + "=" * 50)
    # print("所有信息获取完成！")

    # vm = VoiceManager()
    #
    # def run():
    #     vm.play_voice(vm.collect_speakers(5))
    #
    # threading.Thread(target=run).start()
    #
    # time.sleep(1)
    #
    # vm.break_collect()

    dm = DiskManager()
    print(dm.get_disks())
    print(dm.get_dir_items(r"F:\PythonProject\python_Zorn\Zorn\远程仓库"))
    print(dm.get_item_time(r"F:\PythonProject\python_Zorn\Zorn\远程仓库"))
    print(dm.get_file_size(r"F:\PythonProject\python_Zorn\Zorn\远程仓库\界面.py"))
    print(dm.get_item_type(r"F:\PythonProject\python_Zorn\Zorn\远程仓库"))
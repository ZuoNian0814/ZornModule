import os
import shutil
import sys
import time
import winreg
import ctypes
from ctypes import wintypes

# Windows API 定义
LRESULT = ctypes.c_long
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

user32.SendMessageTimeoutW.restype = LRESULT
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCSTR,
    wintypes.UINT, wintypes.UINT, wintypes.LPVOID
]
shell32.IsUserAnAdmin.restype = wintypes.BOOL

class EnvInstaller:
    def __init__(self, env:dict):
        r"""
        env = {
            "MY_APP_PATH": r"C:\Program Files\MyCustomApp",
        },
        """
        if not self._refresh_env():
            print(f">>> 管理员未启用")
        self.env = env

    def is_admin(self):
        """私有：检查管理员权限"""
        try:
            return shell32.IsUserAnAdmin()
        except:
            return False

    def _refresh_env(self):
        """私有：刷新系统环境变量"""
        user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, b"Environment", 0x0002, 1000, None)

    def add_env(self):
        """私有：批量添加环境变量"""
        try:
            for name in self.env:
                print(f">>> {name}: {os.getenv(name)}")

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            )
            for name, value in self.env.items():
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
                os.environ[name] = str(value)  # <--- 只加这一行，让当前进程能读到
                print(f"✅ 环境变量：{name}")
            winreg.CloseKey(key)
            self._refresh_env()

            for name in self.env:
                print(f">>> {name}: {os.getenv(name)}")

        except Exception as e:
            print(f"❌ 环境变量失败：{e}")

    def remove_env(self):
        """私有：删除环境变量"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0, winreg.KEY_READ | winreg.KEY_SET_VALUE
            )
            for name in self.env.keys():
                try:
                    winreg.DeleteValue(key, name)
                    if name in os.environ:
                        del os.environ[name]  # <--- 只加这一行，同步清理进程变量
                    print(f"✅ 删除变量：{name}")
                except FileNotFoundError:
                    print(f"ℹ️ 变量不存在：{name}")
            winreg.CloseKey(key)
            self._refresh_env()
        except Exception as e:
            print(f"❌ 清理变量失败：{e}")

class FileAssociationManager:
    def __init__(self, ext_config: dict, PROG_PREFIX="ZornCustomExt"):
        # 前缀（自动生成独立PROG_ID，避免冲突）
        self.PROG_PREFIX = PROG_PREFIX
        self.ext_config = self._validate(ext_config)

    def _validate(self, cfg):
        """校验配置合法性"""
        for ext, (exe, ico) in cfg.items():
            if not ext.startswith("."):
                raise ValueError(f"后缀错误：{ext} 必须以 . 开头")
        return cfg

    def _safe_del(self, root, path):
        """安全删除注册表项"""
        try:
            winreg.DeleteKey(root, path)
        except FileNotFoundError:
            pass

    def _get_reg(self, path):
        """读取注册表默认值"""
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path) as key:
                return winreg.QueryValue(key, "")
        except:
            return "未配置"

    # ===================== 核心功能 =====================
    def add_associations(self):
        """批量添加：每个后缀独立图标+程序"""
        try:
            for ext, (exe, icon) in self.ext_config.items():
                prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"  # 生成独立ID
                cmd = fr'"{exe}" "%1"'

                # 1. 后缀 → 独立PROG_ID
                with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ext) as k:
                    winreg.SetValue(k, "", winreg.REG_SZ, prog_id)

                # 2. PROG_ID：配置名称+图标+打开命令（系统标准位置）
                with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, prog_id) as prog:
                    winreg.SetValue(prog, "", winreg.REG_SZ, f"Zorn File")

                    # 独立图标
                    with winreg.CreateKey(prog, "DefaultIcon") as icon_key:
                        winreg.SetValue(icon_key, "", winreg.REG_SZ, icon)

                    # 独立打开程序
                    with winreg.CreateKey(prog, r"shell\open\command") as cmd_key:
                        winreg.SetValue(cmd_key, "", winreg.REG_SZ, cmd)

            print("\n✅ 所有后缀绑定成功！（独立图标+独立程序）")
            self.query_associations()

        except PermissionError:
            print("❌ 错误：请【以管理员身份运行】")

    def remove_associations(self):
        """彻底移除所有绑定（无残留）"""
        try:
            # 删除所有后缀 + 对应的PROG_ID
            for ext in self.ext_config.keys():
                self._safe_del(winreg.HKEY_CLASSES_ROOT, ext)
                prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"
                self._safe_del(winreg.HKEY_CLASSES_ROOT, fr"{prog_id}\shell\open\command")
                self._safe_del(winreg.HKEY_CLASSES_ROOT, fr"{prog_id}\shell\open")
                self._safe_del(winreg.HKEY_CLASSES_ROOT, fr"{prog_id}\shell")
                self._safe_del(winreg.HKEY_CLASSES_ROOT, fr"{prog_id}\DefaultIcon")
                self._safe_del(winreg.HKEY_CLASSES_ROOT, prog_id)

            print("✅ 已彻底移除所有绑定！")
        except Exception as e:
            print(f"❌ 移除失败：{e}")

    def query_associations(self):
        """查询所有绑定（核对图标/程序是否正确）"""
        print("\n" + "="*60)
        print("📋 当前绑定详情（每个后缀独立配置）")
        print("="*60)
        for ext, (exe, icon) in self.ext_config.items():
            prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"
            print(f"\n📌 后缀：{ext}")
            print(f"🖼️  图标：{self._get_reg(f'{prog_id}\\DefaultIcon')}")
            print(f"🚀 程序：{self._get_reg(f'{prog_id}\\shell\\open\\command')}")
            print("-" * 50)

if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        sys.exit("❌ 仅支持Windows")

    # 创建环境变量 ==========================================
    ENV_VALUE = {
        "ENV_KEYS": '[["Blowfish", "5A 6F 72 6E 31 30 32 37"]]',
    }
    env = EnvInstaller(ENV_VALUE)
    # 增改
    env.add_env()
    # # 删
    # env.remove_env()

    # # 绑定图标关系 ============================================
    # FILE_CONFIG = {
    #     ".zorn": (
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\ZornUnpacker.exe",
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\icon\file_icon.ico"
    #     ),
    #     ".zorns": (
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\ZornUnpacker.exe",
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\icon\file_s_icon.ico"
    #     ),
    #     ".zornf": (
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\ZornUnpacker.exe",
    #         r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\icon\folder_icon.ico"
    #     ),
    # }
    #
    # manager = FileAssociationManager(FILE_CONFIG, PROG_PREFIX="ZornCustomExt")
    # # 增改
    # manager.add_associations()
    # # 删
    # manager.remove_associations()
    # # 查
    # manager.query_associations()


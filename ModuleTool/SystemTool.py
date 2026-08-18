import os.path
import winreg
import sys
import ctypes

# 程序图标管理 Windows
class FileAssociationManager:
    def __init__(self, PROG_PREFIX):
        self.PROG_PREFIX = PROG_PREFIX
        # 强制访问64位注册表视图，避免32位Python在64位系统上出现视图错位
        self._sam_flag = winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY

    def _get_reg(self, path):
        """读取注册表默认值"""
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path, 0, self._sam_flag) as key:
                return winreg.QueryValue(key, "")
        except:
            return None

    def _delete_reg_tree(self, root, sub_key):
        """递归删除注册表项及所有子项，彻底解决含子键无法删除的问题"""
        try:
            with winreg.OpenKey(root, sub_key, 0, self._sam_flag) as key:
                index = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, index)
                        # 先递归删除所有子项
                        self._delete_reg_tree(root, f"{sub_key}\\{subkey_name}")
                    except OSError:
                        break
                    index += 1
            # 所有子项清空后，删除当前项
            winreg.DeleteKeyEx(root, sub_key, self._sam_flag, 0)
        except FileNotFoundError:
            pass

    def add_associations(self, ext_config):
        """批量添加：每个后缀独立图标+程序"""
        try:
            for ext, config in ext_config.items():
                icon = config.get("icon")
                if not os.path.isfile(icon):
                    print(f"{icon} 不存在")
                    continue
                exe = config.get("exe")
                if ext[0] != ".":
                    ext = "." + ext
                prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"

                with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, ext, 0, self._sam_flag) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, prog_id)
                with winreg.CreateKeyEx(winreg.HKEY_CLASSES_ROOT, prog_id, 0, self._sam_flag) as prog:
                    winreg.SetValueEx(prog, "", 0, winreg.REG_SZ, f"{ext} File")
                    with winreg.CreateKeyEx(prog, "DefaultIcon", 0, self._sam_flag) as icon_key:
                        winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, icon)
                    if exe:
                        if not os.path.isfile(exe):
                            print(f"{exe} 不存在")
                            continue
                        cmd = fr'"{exe}" "%1"'
                        with winreg.CreateKeyEx(prog, r"shell\open\command", 0, self._sam_flag) as cmd_key:
                            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
            self.query_associations()
            return None
        except PermissionError as e:
            print("❌ 错误：权限不足，请确认已授权管理员权限")
            return e
        except Exception as e:
            print(f"❌ 添加注册项失败：{e}")
            return e

    def remove_associations(self, ext_list=[]):
        """彻底移除所有绑定（递归删除无残留）"""
        try:
            for ext in ext_list:
                # 删除后缀项
                self._delete_reg_tree(winreg.HKEY_CLASSES_ROOT, ext)
                # 删除对应的PROG_ID完整项
                prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"
                self._delete_reg_tree(winreg.HKEY_CLASSES_ROOT, prog_id)
            return None
        except PermissionError as e:
            print(fr"❌ 权限不足，请确保以管理员身份运行或手动删除注册表：计算机\HKEY_CURRENT_USER\Software\Classes\{self.PROG_PREFIX}")
            return e
        except Exception as e:
            print(f"❌ 移除失败：{e}")
            return e

    def query_associations(self, ext_list=[]):
        """查询所有绑定详情"""
        results = {}
        for ext in ext_list:
            if ext[0] != ".":
                ext = "." + ext
            prog_id = f"{self.PROG_PREFIX}_{ext[1:]}"
            results[ext] = {
                "PROG_PREFIX": self.PROG_PREFIX,
                "icon": self._get_reg(f'{prog_id}\\DefaultIcon'),
                "exe": self._get_reg(f'{prog_id}\\shell\\open\\command'),
            }
        return results

if __name__ == "__main__":
    # 计算机\HKEY_CURRENT_USER\Software\Classes\ZornCustomExt_zorn
    if not sys.platform.startswith("win"):
        sys.exit("❌ 仅支持Windows系统")

    FILE_CONFIG = {
        ".zorn": (
            r"F:\PythonProject\python_Zorn\加密存储\Zcret\Zcret.exe",
            r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\icon\file_icon.ico"
        ),
        ".zorns": (
            r"F:\PythonProject\python_Zorn\加密存储\Zcret\Zcret.exe",
            r"F:\PythonProject\python_人工智能自动化\软件自动化智能体\icon\file_s_icon.ico"
        )
    }

    manager = FileAssociationManager("ZornCustomExt")

    # manager.add_associations(FILE_CONFIG)
    # manager.remove_associations()
    results = manager.query_associations([".zorn", ".zorns"])
    print(results)

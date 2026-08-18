from pynput import keyboard
from pynput.keyboard import Key, Controller, KeyCode
import time
from pynput.mouse import Controller as MouseCtrl, Button

class MouseController:
    """
    鼠标操作封装类（永久固定接口）
    仅提供单键按下/松开 + 移动 + 滚轮，无任何封装逻辑
    """
    def __init__(self):
        self.mouse = MouseCtrl()

    # ===================== 左键操作 =====================
    def left_down(self):
        """左键按下（不松开）"""
        self.mouse.press(Button.left)

    def left_up(self):
        """左键松开"""
        self.mouse.release(Button.left)

    # ===================== 右键操作 =====================
    def right_down(self):
        """右键按下（不松开）"""
        self.mouse.press(Button.right)

    def right_up(self):
        """右键松开"""
        self.mouse.release(Button.right)

    # ===================== 中键操作 =====================
    def middle_down(self):
        """中键按下（不松开）"""
        self.mouse.press(Button.middle)

    def middle_up(self):
        """中键松开"""
        self.mouse.release(Button.middle)

    # ===================== 鼠标移动 =====================
    def move_to(self, x: int, y: int):
        """绝对移动：移动到屏幕指定坐标 (x, y)"""
        self.mouse.position = (x, y)

    def move(self, dx: int, dy: int):
        """相对移动：从当前位置偏移 dx(水平) dy(垂直)"""
        self.mouse.move(dx, dy)

    # ===================== 鼠标滚轮 =====================
    def scroll(self, vertical: int, horizontal: int = 0):
        """
        滚轮控制
        :param vertical: 垂直滚动（正数=向上，负数=向下）
        :param horizontal: 水平滚动（正数=向右，负数=向左）
        """
        self.mouse.scroll(horizontal, vertical)

class KeyboardListener:
    def __init__(self, on_key_press, on_key_release):
        self.listener = None
        self.on_key_press = on_key_press
        self.on_key_release = on_key_release

        # 全按键映射表
        self.KEY_MAP = {
            # 修饰键
            keyboard.Key.ctrl_l: "ctrl",
            keyboard.Key.ctrl_r: "ctrl",
            keyboard.Key.shift_l: "shift",
            keyboard.Key.shift_r: "shift",
            keyboard.Key.alt_l: "alt",
            keyboard.Key.alt_r: "alt",
            # 基础键
            keyboard.Key.enter: "enter",
            keyboard.Key.esc: "esc",
            keyboard.Key.space: "space",
            keyboard.Key.backspace: "backspace",
            keyboard.Key.tab: "tab",
            keyboard.Key.caps_lock: "caps_lock",
            # 编辑键
            keyboard.Key.insert: "insert",
            keyboard.Key.delete: "delete",
            keyboard.Key.home: "home",
            keyboard.Key.end: "end",
            keyboard.Key.page_up: "page_up",
            keyboard.Key.page_down: "page_down",
            # 方向键
            keyboard.Key.up: "up",
            keyboard.Key.down: "down",
            keyboard.Key.left: "left",
            keyboard.Key.right: "right",
            # F1-F12
            keyboard.Key.f1: "f1", keyboard.Key.f2: "f2", keyboard.Key.f3: "f3",
            keyboard.Key.f4: "f4", keyboard.Key.f5: "f5", keyboard.Key.f6: "f6",
            keyboard.Key.f7: "f7", keyboard.Key.f8: "f8", keyboard.Key.f9: "f9",
            keyboard.Key.f10: "f10", keyboard.Key.f11: "f11", keyboard.Key.f12: "f12",
            # Ctrl组合字符
            "\x03": "c", "\x16": "v", "\x01": "a", "\x18": "x", "\x1a": "z"
        }

        # 🔥 绝杀修复：虚拟键码字符串映射（<187> → plus）
        self.VK_STR_MAP = {
            "<187>": "plus",      # + = 键
            "<189>": "minus",     # - _ 键
            "<219>": "lbracket",
            "<221>": "rbracket",
            "<186>": "semicolon",
            "<222>": "quote",
            "<188>": "comma",
            "<190>": "period",
            "<191>": "slash",
            "<220>": "backslash",
        }

    def _normalize_key(self, key):
        # 🔥 第一步：强制拦截 <187> 这类虚拟键字符串（核心修复）
        key_str = str(key)
        if key_str in self.VK_STR_MAP:
            return self.VK_STR_MAP[key_str]

        # 第二步：处理普通字符
        try:
            char = key.char.lower()
            return self.KEY_MAP.get(char, char)
        except AttributeError:
            pass

        # 第三步：处理功能键
        return self.KEY_MAP.get(key, key_str)

    def _on_press(self, key):
        key_name = self._normalize_key(key)
        self.on_key_press(key_name)

    def _on_release(self, key):
        key_name = self._normalize_key(key)
        self.on_key_release(key_name)

    def start(self):
        if not self.listener or not self.listener.is_alive():
            self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()

class KeyboardSimulator:
    def __init__(self):
        self.controller = Controller()
        # 🔥 与监听类完全同步，全按键映射
        self.KEY_MAP = {
            # 修饰键
            "ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt,
            # 基础控制键
            "enter": Key.enter, "esc": Key.esc, "space": Key.space,
            "backspace": Key.backspace, "tab": Key.tab, "caps_lock": Key.caps_lock,
            # 编辑键
            "insert": Key.insert, "delete": Key.delete, "home": Key.home,
            "end": Key.end, "page_up": Key.page_up, "page_down": Key.page_down,
            # 方向键
            "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
            # 功能键
            "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4, "f5": Key.f5,
            "f6": Key.f6, "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10,
            "f11": Key.f11, "f12": Key.f12,
            # ===================== 特殊符号键（对应监听类）=====================
            "plus": KeyCode(187),      # + = 键
            "minus": KeyCode(189),     # - _ 键
            "lbracket": KeyCode(219),  # [ {
            "rbracket": KeyCode(221),  # ] }
            "semicolon": KeyCode(186), # ; :
            "quote": KeyCode(222),     # ' "
            "comma": KeyCode(188),     # , <
            "period": KeyCode(190),    # . >
            "slash": KeyCode(191),     # / ?
            "backslash": KeyCode(220), # \ |
        }

    # 固定方法：单个按键按下（永不修改）
    def key_down(self, key_name):
        try:
            key = self.KEY_MAP.get(key_name, key_name)
            self.controller.press(key)
            time.sleep(0.01)
        except:
            pass

    # 固定方法：单个按键松开（永不修改）
    def key_up(self, key_name):
        try:
            key = self.KEY_MAP.get(key_name, key_name)
            self.controller.release(key)
            time.sleep(0.01)
        except:
            pass

if __name__ == '__main__':
    # ===================== 单独使用监听类 ================================================================
    def press_callback(key_str):
        print(f"📥 监听按下：{key_str}")  # 输出标准字符串


    def release_callback(key_str):
        print(f"📤 监听松开：{key_str}")

    # 创建监听对象
    listener = KeyboardListener(press_callback, release_callback)
    listener.start()  # 启动123321a

    time.sleep(10)
    listener.stop()

    # ===================== 单独使用模拟类 ============================================================
    simulator = KeyboardSimulator()
    # ------------------- 单键模拟 -------------------
    simulator.key_down("a")
    simulator.key_up("a")
    # ------------------- 组合键：Ctrl+C（手动调用单键） -------------------
    simulator.key_down("ctrl")  # 按下Ctrl
    simulator.key_down("c")  # 按下C
    simulator.key_up("c")  # 松开C
    simulator.key_up("ctrl")  # 松开Ctrl
    # ------------------- 三键组合：Ctrl+Shift+A -------------------
    simulator.key_down("ctrl")
    simulator.key_down("shift")
    simulator.key_down("a")
    simulator.key_up("a")
    simulator.key_up("shift")
    simulator.key_up("ctrl")

    # ===================== 鼠标模拟类 ===================================================================
    # 初始化鼠标对象（固定类名）
    mouse = MouseController()

    # ------------------- 1. 基础单键点击（左键单击） -------------------
    mouse.left_down()
    mouse.left_up()

    # ------------------- 2. 系统双击（外部加延迟，由系统识别） -------------------
    mouse.left_down()
    mouse.left_up()
    time.sleep(0.1)  # 手动控制延迟
    mouse.left_down()
    mouse.left_up()

    # ------------------- 3. 右键单击 -------------------
    mouse.right_down()
    mouse.right_up()

    # ------------------- 4. 鼠标移动 -------------------
    mouse.move_to(500, 500)  # 绝对移动到 (500,500)
    mouse.move(100, 0)  # 相对移动：向右100像素

    # ------------------- 5. 鼠标滚轮 -------------------
    mouse.scroll(120)  # 向上滚动
    mouse.scroll(-80)  # 向下滚动

    # ------------------- 6. 拖拽操作（按住左键移动） -------------------
    mouse.move_to(200, 200)
    mouse.left_down()
    time.sleep(0.05)
    mouse.move(300, 300)
    mouse.left_up()
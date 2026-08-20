import json
import socket
import threading
import queue
import struct
import time
import uuid

# 全局常量定义（仅需修改这里即可统一调整包头长度）
HEADER_LENGTH = 8  # 包头占用字节数：4字节 = 32位整数
HEADER_FORMAT = '>Q'  # 对应32位无符号大端整数
"""
用途	HEADER_FORMAT	HEADER_LENGTH	整数位数	最大支持数据长度
1 字节长度头（极小包）	>B	1	8 位	255 字节
2 字节长度头（小包）	>H	2	16 位	65KB
4 字节长度头（通用）	>I	4	32 位	4GB
8 字节长度头（超大包）	>Q	8	64 位	无限（1.8 亿 TB）
"""
MAX_PACKET_SIZE = 5 * 1024 ** 2  # 单包最大长度5MB

# 通用工具函数
def pack_data(data: bytes) -> bytes:
    """打包：固定长度包头+数据，解决粘包"""
    header = struct.pack(HEADER_FORMAT, len(data))
    return header + data

# 响应标记
def response(func):
    """装饰器：标记该方法允许被 request 调用"""
    func.__response__ = True  # 给方法打一个隐藏标记
    return func

# 服务器类
class Server:
    def __init__(self,
            ip: str = '127.0.0.1', port: int = 10276, maxsize=0, threading_nums=1
        ):
        self.threading_nums = threading_nums
        self.ip = ip
        self.port = int(port)
        self.clients = {}
        self.server_socket = None
        self.running = False
        self.send_queue = queue.Queue()
        self.recv_queue = queue.Queue(maxsize=maxsize)

        # 钩子函数
        self.start_hook = []
        self.close_hook = []
        self.connect_hook = []
        self.disconnect_hook = []

        # 响应处理
        self.responses = {}
        self.response_waite = {}

    def start(self):
        """启动服务器（接口不变）"""
        if self.running:
            return
        self.running = True

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen()

        threading.Thread(target=self._run_server, daemon=True).start()
        threading.Thread(target=self._send_thread, daemon=True).start()
        for i in range(self.threading_nums):
            threading.Thread(target=self._handle_thread, daemon=True).start()

        for function, args, kwargs in self.start_hook:
            function(*args, **kwargs)
        print(f"[服务器] 启动 | IP:{self.ip} 端口:{self.port}")

    def bind_start_hook(self, function, *args, **kwargs):
        self.start_hook.append((function, args, kwargs))

    # 监听连接
    def _run_server(self):
        """监听连接，为每个客户端生成终身唯一ID"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                client_ip = addr[0]
                # 生成全局唯一ID
                client_id = str(uuid.uuid4())
                self.clients[client_id] = {"socket": conn, "ip": client_ip}
                print(f"[服务器] 新连接 | ID:{client_id} | IP:{client_ip}")
                # 启动专属接收线程（仅传唯一ID）
                threading.Thread(target=self._recv_client, args=(conn, client_id), daemon=True).start()
                for function, args, kwargs in self.connect_hook:
                    # print(function, args, kwargs)
                    function(client_id, *args, **kwargs)
            except (socket.error, OSError):
                break

    def bind_connect_hook(self, function, *args, **kwargs):
        """function 必须存在一个 client_id 字段在第一位"""
        self.connect_hook.append((function, args, kwargs))

    def _recv_client(self, client_socket: socket.socket, client_id: str):
        """客户端接收线程：仅用唯一ID标识"""
        while self.running:
            try:
                header = self._recvall(client_socket, HEADER_LENGTH)
                if not header: break
                data_len = struct.unpack(HEADER_FORMAT, header)[0]
                data = self._recvall(client_socket, data_len)
                if not data: break
                self.recv_queue.put((client_id, data))
            except Exception:
                break
        self._remove_client(client_id)

    def _send_thread(self):
        """发送线程：从队列取【唯一ID】发送数据"""
        while self.running:
            client_id = None
            try:
                # 队列格式：(客户端ID, 数据)
                client_id, data = self.send_queue.get(timeout=1)
                if client_id not in self.clients: continue
                packed_data = pack_data(data)
                self.clients[client_id]["socket"].sendall(packed_data)
            except queue.Empty:
                continue
            except Exception:
                self._remove_client(client_id)

    def bind_disconnect_hook(self, function, *args, **kwargs):
        self.disconnect_hook.append((function, args, kwargs))

    def _handle_thread(self):
        """处理线程：回调【唯一ID】，精准区分客户端"""
        while self.running:
            try:
                client_id, data = self.recv_queue.get(timeout=1)
                # 回调：用唯一ID标识客户端
                self._handle_message(client_id, data)
            except queue.Empty:
                continue

    def _recvall(self, sock: socket.socket, length: int) -> bytes | None:
        data = b""
        while len(data) < length:
            chunk = sock.recv(min(length - len(data), MAX_PACKET_SIZE))
            if not chunk: return None
            data += chunk
        return data

    def _remove_client(self, client_id: str):
        """清理客户端（唯一ID）"""
        if client_id in self.clients:
            info = self.clients[client_id]
            try: info["socket"].close()
            except: pass
            ip = info["ip"]
            for function, args, kwargs in self.disconnect_hook:
                function(client_id, *args, **kwargs)
            try:
                del self.clients[client_id]
            except KeyError: pass
            print(f"[服务器] 断开 | ID:{client_id} | IP:{ip}")

    #  核心对外接口（唯一ID）
    def send_to(self, client_id: str, data: bytes, handle=False):
        """
        向【指定唯一ID】的客户端发消息
        （同一主机的多个客户端，ID不同，精准发送）
        """
        if client_id in self.clients:
            if handle:
                self.send_queue.put((client_id, self.msg_handle(client_id, data)))
            else:
                self.send_queue.put((client_id, data))

    # 可被继承的处理方式
    def msg_handle(self, client_id, data):
        return data

    def send_to_json(self, client_id, json_data, handle=False):
        json_data_b = json.dumps(json_data, ensure_ascii=False).encode()
        self.send_to(client_id, json_data_b, handle)

    # 请求式消息案例
    @response
    def version(self, client_id):
        return 3.0

    # 请求方法，用户可直接调用
    def request(self, client_id, name, headers={}, timeout=5):
        message = {
            "type": "__request__",
            "_name": name,
            "_headers": headers
        }
        message_b = json.dumps(message, ensure_ascii=False).encode()
        self.send_to(client_id, message_b)
        # 添加入等待队列并临时阻塞
        self.response_waite[(client_id, name)] = 0.0
        while (client_id, name) in self.response_waite:
            time.sleep(0.01)
            self.response_waite[(client_id, name)] += 0.01
            # 响应超时
            if self.response_waite[(client_id, name)] >= timeout:
                del self.response_waite[(client_id, name)]
                return {"error": "Timeout."}
            # 出现响应
            if (client_id, name) in self.responses:
                result = self.responses[(client_id, name)]
                # 清空等待列表
                del self.responses[(client_id, name)]
                del self.response_waite[(client_id, name)]
                return result

        return {"error": "Unknown error."}

    # 响应请求方法，结果转发给对方
    def _response(self, client_id, name, **headers):
        try:
            method = getattr(self, name)
            if not getattr(method, '__response__', False):  # 如果请求不存在
                message = {
                    "type": "__response__",
                    "name": name,
                    "result": {"error": "Invalid request"}
                }
                message_b = json.dumps(message, ensure_ascii=False).encode()
                self.send_to(client_id, message_b)
                return

            result = method(client_id, **headers)
            message = {
                "type": "__response__",
                "name": name,
                "result": result
            }
            message_b = json.dumps(message, ensure_ascii=False).encode()
            self.send_to(client_id, message_b)
        except Exception as e:
            message = {
                "type": "__response__",
                "name": name,
                "result": {"error": f"{e}"}
            }
            message_b = json.dumps(message, ensure_ascii=False).encode()
            self.send_to(client_id, message_b)

    # 内部消息处理，用于辨认请求/响应/和普通消息
    def _handle_message(self, client_id: str, msg: bytes):
        try:
            message = json.loads(msg.decode())
            message_type = message.get("type")
            if message_type == "__request__":
                name = message.get("_name")
                headers = message.get("_headers")
                self._response(client_id, name, **headers)
            # 处理响应
            elif message_type == "__response__":
                name = message.get("name")
                result = message.get("result")
                if (client_id, name) in self.response_waite:
                    self.responses[(client_id, name)] = result
            else:
                self.handle_message(client_id, msg)
        except:
            self.handle_message(client_id, msg)

    # 用于让用户覆写的消息处理方法
    def handle_message(self, client_id: str, msg: bytes):
        """
        消息回调：参数=【客户端唯一ID】+ 数据
        你可以精准知道是哪个客户端发的消息
        """
        print(f"[服务器] 客户端{client_id} 消息：{msg[:100]}")

    def close(self):
        """关闭服务器（接口不变）"""
        if not self.running: return
        self.running = False
        for cid in list(self.clients.keys()):
            self._remove_client(cid)
        try:
            if self.server_socket: self.server_socket.close()
        except: pass

        for function, args, kwargs in self.close_hook:
            function(*args, **kwargs)
        print("[服务器] 已关闭")

    def bind_close_hook(self, function, *args, **kwargs):
        self.close_hook.append((function, args, kwargs))

# 客户端类
class Client:
    def __init__(self, server_ip: str, server_port: int, maxsize=0):
        self.server_ip = server_ip
        self.server_port = int(server_port)
        self.client_socket = None
        self.running = False
        # 线程安全队列
        self.send_queue = queue.Queue(maxsize=maxsize)
        self.recv_queue = queue.Queue()

        self.start_hook = []
        self.close_hook = []
        self.connect_hook = []

        # 新增：响应处理（客户端无需client_id，仅用方法名做键）
        self.responses = {}
        self.response_waite = {}

    def start(self):
        """启动客户端（独立线程，不阻塞主进程）"""
        if self.running:
            return
        self.running = True

        for function, args, kwargs in self.start_hook:
            function(*args, **kwargs)

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_ip, self.server_port))

        # 启动核心守护线程
        threading.Thread(target=self._recv_thread, daemon=True).start()
        threading.Thread(target=self._send_thread, daemon=True).start()
        threading.Thread(target=self._handle_thread, daemon=True).start()
        print(f"[客户端] 连接服务器成功 | {self.server_ip}:{self.server_port}")

        for function, args, kwargs in self.connect_hook:
            function(*args, **kwargs)

    def bind_start_hook(self, function, *args, **kwargs):
        self.start_hook.append((function, args, kwargs))

    def bind_connect_hook(self, function, *args, **kwargs):
        self.connect_hook.append((function, args, kwargs))

    def _recv_thread(self):
        """独立接收线程：接收服务器数据"""
        while self.running:
            try:
                header = self._recvall(HEADER_LENGTH)
                if not header:
                    break
                data_len = struct.unpack(HEADER_FORMAT, header)[0]
                data = self._recvall(data_len)
                if not data:
                    break
                self.recv_queue.put(data)
            except Exception:
                break
        self.close()

    def _send_thread(self):
        """异步发送线程：循环处理发送队列"""
        while self.running:
            try:
                data = self.send_queue.get(timeout=1)
                packed_data = pack_data(data)
                self.client_socket.sendall(packed_data)
            except queue.Empty:
                continue
            except Exception:
                break
        self.close()

    def _handle_thread(self):
        """消息处理线程：从队列取数据并执行handle_message"""
        while self.running:
            try:
                data = self.recv_queue.get(timeout=1)
                # 修改：调用内部消息处理，解析请求/响应
                self._handle_message(data)
            except queue.Empty:
                continue

    def _recvall(self, length: int) -> bytes | None:
        """循环接收指定长度的字节数据"""
        data = b""
        while len(data) < length:
            chunk = self.client_socket.recv(min(length - len(data), MAX_PACKET_SIZE))
            if not chunk:
                return None
            data += chunk
        return data

    def send(self, data: bytes, handle=False):
        """向服务器发送数据（仅入队列，异步发送）"""

        if handle:
            self.send_queue.put(self.msg_handle(data))
        else:
            self.send_queue.put(data)

    def msg_handle(self, data):
        return data

    # 新增：JSON数据发送快捷方法
    def send_json(self, json_data, handle=False):
        json_data_b = json.dumps(json_data, ensure_ascii=False).encode()
        self.send(json_data_b, handle=handle)

    # 新增：客户端发起请求（调用服务器方法）
    def request(self, name, headers={}, timeout=5):
        message = {
            "type": "__request__",
            "_name": name,
            "_headers": headers
        }
        self.send_json(message)
        # 添加入等待队列
        self.response_waite[name] = 0.0
        while name in self.response_waite:
            time.sleep(0.01)
            self.response_waite[name] += 0.01
            # 响应超时
            if self.response_waite[name] >= timeout:
                del self.response_waite[name]
                return {"error": "Timeout."}
            # 收到响应
            if name in self.responses:
                result = self.responses[name]
                del self.responses[name]
                del self.response_waite[name]
                return result
        return {"error": "Unknown error."}

    # 新增：处理服务器发来的请求
    def _response(self, name, **headers):
        try:
            method = getattr(self, name)
            if not getattr(method, '__response__', False):
                message = {
                    "type": "__response__",
                    "name": name,
                    "result": {"error": "Invalid request"}
                }
                self.send_json(message)
                return
            result = method(**headers)
            message = {
                "type": "__response__",
                "name": name,
                "result": result
            }
            self.send_json(message)
        except Exception as e:
            message = {
                "type": "__response__",
                "name": name,
                "result": {"error": str(e)}
            }
            self.send_json(message)

    # 新增：内部消息处理，解析请求/响应
    def _handle_message(self, msg: bytes):
        try:
            message = json.loads(msg.decode())
            message_type = message.get("type")
            if message_type == "__request__":
                # 处理服务器发起的请求
                name = message.get("_name")
                headers = message.get("_headers", {})
                self._response(name, **headers)
            elif message_type == "__response__":
                # 处理响应，仅保留等待中的消息，过滤过期脏数据
                name = message.get("name")
                result = message.get("result")
                if name in self.response_waite:
                    self.responses[name] = result
            else:
                self.handle_message(msg)
        except:
            # 异常走普通消息处理
            self.handle_message(msg)

    def handle_message(self, msg: bytes):
        """消息处理：输出前100字节，可自定义扩展"""
        print(f"[客户端] 收到消息（前100字节）：{msg[:100]}")

    def close(self):
        """断开连接，释放资源"""
        if not self.running:
            return
        self.running = False
        try:
            self.client_socket.close()
        except:
            pass
        print("[客户端] 已断开连接")
        for function, args, kwargs in self.close_hook:
            function(*args, **kwargs)

    def bind_close_hook(self, function, *args, **kwargs):
        self.close_hook.append((function, args, kwargs))

# 使用示例 ========================================
class ServerTest(Server):
    def __init__(self, ip='127.0.0.1', port=10274):
        super().__init__(ip, port)

    # 自定义请求式消息
    @response
    def addition(self, m, n):
        return m + n

    # 覆写父类的消息处理方法（接收时自动触发）
    def handle_message(self, client_id, msg):
        print(f"【覆写后】服务器接收到客户端【{client_id}】的消息：{msg.decode()}")

class ClientTest(Client):
    def __init__(self, server_ip='127.0.0.1', server_port=10274):
        super().__init__(server_ip, server_port)

    # 自定义请求式消息
    @response
    def multiplication(self, m, n):
        return m * n

    # 覆写父类的消息处理方法（接收时自动触发）
    def handle_message(self, msg):
        print(f"【覆写后】客户端接收到【服务器】的消息：{msg.decode()}")

# ==================== 测试示例 ====================
if __name__ == '__main__':
    # 普通钩子函数
    def hook_function(nums, messages):
        print(f"hook[{nums}]: {messages}")

    # 服务器连接时的钩子函数（须包含client_id字段）
    def server_hook_function(client_id, nums, messages):
        print(f"hook[{nums}] from:{client_id} | {messages}")

    # 实例化服务器
    server = ServerTest()
    # 绑定钩子函数
    server.bind_start_hook(hook_function, 0, "服务器开启")   # 开启时触发
    server.bind_connect_hook(server_hook_function, 1, "服务器的新连接")   # 连接时触发
    server.bind_close_hook(hook_function, 2, "服务器关闭")   # 关闭时触发
    server.start()  # 开启服务器

    # 实例化客户端
    client = ClientTest()
    # 绑定钩子函数
    client.bind_start_hook(hook_function, 3, "客户端开启")   # 开启时触发
    client.bind_connect_hook(hook_function, 4, "客户端连接成功")  # 连接时触发
    client.bind_close_hook(hook_function, 5, "客户端关闭")    # 关闭时触发
    client.start()  # 开启客户端

    # 获取客户端列表
    client_id = list(server.clients.keys())[0]
    server.send_to(client_id, "服务器发送的消息测试".encode())    # 发送消息到指定客户端
    time.sleep(0.1) # 独立线程可能同时输出导致print串行，等一会再进行下一步
    client.send("客户端发送的消息测试".encode())          # 发送消息到服务器

    # 尝试请求客户端的乘法函数
    result = server.request(client_id, name="multiplication", headers={"m": 2, "n": 3}, timeout=1)
    print(f"服务器发起的请求结果，理应为6：{result}")

    # 尝试请求服务器的加法函数
    result = client.request(name="addition", headers={"m": 2, "n": 3}, timeout=1)
    print(f"客户端发起的请求结果，理应为5：{result}")

    client.close()
    time.sleep(0.1) # 近乎同时关闭可能导致客户端池清理报错，短暂停顿
    server.close()

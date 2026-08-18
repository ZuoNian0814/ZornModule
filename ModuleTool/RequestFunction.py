import json
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
import requests

def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

function_map = {"get_time": get_time}

class FlaskServer:
    def __init__(self):
        self.app = Flask(__name__)
        self.host = "127.0.0.1"
        self.port = 5000
        self.server = None
        # 单一路由 + 路径参数接收 tool_name
        self.app.add_url_rule('/<tool_name>', view_func=self.handle_request)

    # 统一处理函数：读取路径tool_name + 请求参数
    def handle_request(self, tool_name):
        print({"tool_name": tool_name, "params": dict(request.args)})
        function = function_map[tool_name]
        result = function(**dict(request.args))
        return jsonify(result)

    # 启动服务器
    def start(self):
        self.server = make_server(self.host, self.port, self.app)
        self.server.serve_forever()

    # 关闭服务器
    def stop(self):
        self.server.shutdown()

def request_function(tool_call_id, tool_name, args):
    url = f"http://127.0.0.1:5000/{tool_name}"
    res = requests.get(url, params=args)
    print(res.json())
    return {'tool_call_id': tool_call_id, 'tool_name': tool_name, 'result': res.json()}

if __name__ == "__main__":
    server = FlaskServer()
    server.start()



# coding: utf-8
import _thread as thread
import base64
import hashlib
import hmac
import json
import os
from typing import Dict, Any

import requests
import ssl
import uuid
import websocket
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from urllib.parse import urlparse
from wsgiref.handlers import format_date_time


class IflySparkAgentClient(object):
    """
        任务链客户端,用于通过API调用任务链进行会话
    """

    # 初始化
    def __init__(self,
                 base_url: str = os.getenv("IFLY_SPARK_AGENT_BASE_URL", "https://flames.iflytek.com:2443"),
                 app_id: str = os.getenv("IFLY_SPARK_AGENT_APP_ID"),
                 app_secret: str = os.getenv("IFLY_SPARK_AGENT_APP_SECRET"),
                 body_id: str = os.getenv("IFLY_SPARK_AGENT_BODY_ID"),
                 ):
        if not base_url:
            raise ValueError("IFLY_SPARK_AGENT_BASE_URL is not set")
        if not app_id:
            raise ValueError("IFLY_SPARK_AGENT_APP_ID is not set")
        if not app_secret:
            raise ValueError("IFLY_SPARK_AGENT_APP_SECRET is not set")

        self.app_id = app_id
        self.app_secret = app_secret
        self.body_id = body_id
        self.base_url = base_url
        self.host = urlparse(self.base_url).hostname
        # chat会话接口地址
        self.chat_endpoint = "/openapi/flames/api/v2/chat"
        # 文件上传接口地址
        self.upload_endpoint = "/openapi/flames/file/v2/upload"
        # 获取智能体信息接口地址
        self.get_process_endpoint = f"/openapi/flames/api/v2/apps/{app_id}/resources"

        # 生成url,拼接API网关核心鉴权签名信息
        # self.flows=self.get_agent_info()

    def create_url(self, method, path, wsProtocol):
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: {}\ndate: {}\n{} {} HTTP/1.1".format(self.host, date, method, path)

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.app_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'hmac api_key="{self.app_id}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host,
            "bodyId": self.body_id
        }
        base_url = self.base_url.replace("https", "wss").replace("http", "ws") if wsProtocol else self.base_url
        # 拼接鉴权参数，生成url
        url = base_url + path + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url

    def upload(self, file_path):
        request_url = self.create_url("POST", self.upload_endpoint, False)
        print("### upload ### request_url:", request_url)
        _, file_name = os.path.split(file_path)
        file = open(file_path, 'rb')
        file_base64_str = base64.b64encode(file.read()).decode('utf-8')
        body = {
            "payload": {
                "fileName": file_name,
                "file": file_base64_str
            }
        }
        response = requests.post(request_url, json=body, headers={'content-type': "application/json"},
                                 verify=False)
        print('response:', response.text)
        data = json.loads(response.text)
        code = data["header"]["code"]
        if code != 0:
            print(f'请求错误: {code}, {data}')
            return
        else:
            file_id = data["payload"]["id"]
        return file_id

    # 建立连接, 生成内容
    def chat_completions(self, agent_info:Dict[str, Any], arguments):
        request_url = self.create_url("GET", self.chat_endpoint, True)
        print("### generate ### request_url:", request_url)
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            request_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        ws.app_id = self.app_id
        ws.body_id = agent_info["body_id"]
        ws.params = {
            "header": {
                "traceId": str(uuid.uuid1()).replace("-", ""),
                "mode": 0,
                "appId": self.app_id,
                "bodyId": agent_info["body_id"]
            },
            "payload": {
                "input": arguments
            }
        }
        ws.run_forever(
            sslopt={
                "cert_reqs": ssl.CERT_NONE
            }
        )

    def get_agent_info(self) -> Dict[str, Any]:
        """
        get flow info, such as flow description, parameters
        :return:
        """
        url = f"{self.base_url}{self.get_process_endpoint}/{self.body_id}"
        headers = {
            "Authorization": f"Bearer {self.app_id}:{self.app_secret}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        if json_data.get("code", 0) != 0:
            raise ValueError(json_data)
        # TODO 处理响应数据
        return json_data

    def upload_file(
            self,
            file_path,
    ) -> Any | None:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.app_id}:{self.app_secret}",
        }
        _, file_name = os.path.split(file_path)
        file = open(file_path, 'rb')
        file_base64_str = base64.b64encode(file.read()).decode('utf-8')
        body = {
            "payload": {
                "fileName": file_name,
                "file": file_base64_str
            }
        }
        request_url = self.create_url("POST", self.upload_endpoint, False)
        print("### upload ### request_url:", request_url)
        response = requests.post(request_url, json=body, headers=headers, verify=False)
        print('response:', response.text)
        response_data = json.loads(response.text)
        code = response_data["header"]["code"]
        if code != 0:
            print(f'请求错误: {code}, {data}')
            return None
        else:
            return response_data["payload"]["id"]

    # 收到websocket错误的处理
    def on_error(self, ws, error):
        print("### on_error:", error)

    # 收到websocket关闭的处理
    def on_close(self, ws, close_status_code, close_msg):
        print("### on_close ### code:", close_status_code, " msg:", close_msg)

    # 收到websocket连接建立的处理
    def on_open(self, ws):
        print("### on_open ###")
        request_params = json.dumps(ws.params)
        print("### request:", request_params)
        ws.send(request_params)

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        # print("### on_message:", message)
        # TODO 处理响应数据
        messageJson = json.loads(message)
        if messageJson["header"]["status"] == 1:
            nodeCode = messageJson["payload"]["output"]["node"]
            nodeRespPayload = messageJson["payload"]["output"]["payload"]
            print("### on_message, nodeCode:", nodeCode, " nodeRespPayload:", nodeRespPayload)



# 入口函数
if __name__ == "__main__":
    TRACE_ID = str(uuid.uuid1()).replace("-", "")
    # 开发平台访问地址
    BASE_URL = "https://172.31.164.103:30009"
    # 应用管理 -> 应用详情 -> AppID(复制)
    APP_ID = "C6E877B5753E46DFB899"
    # 应用管理 -> 应用详情 -> App Secret Key(复制)
    APP_SECRET = "ED9EC9A0D0F9493E8F96205D8A9E933E"
    # 应用管理 -> 应用详情 -> 关联数据列表 -> 编码(复制)
    BODY_ID = "xxxxxxxxxxxxxxxxxxxxxxxxxxx"
    # 初始化客户端
    client = IflySparkAgentClient(APP_ID, APP_SECRET, BASE_URL, BODY_ID)
    # 上传文件,获取文件ID
    file_id = client.upload("scene-file-test.txt")
    # 通过"应用管理->应用详情->关联数据列表->协议"详情获取请求参数
    data = {
        "header": {
            "traceId": TRACE_ID,
            "mode": 0,
            "appId": APP_ID,
            "bodyId": BODY_ID
        },
        "payload": {
            "input": {
                "a2ae8c77d8": {
                    "file": file_id,
                }
            }
        }
    }
    # 生成内容
    client.generate(data)

# coding: utf-8
import base64
import hashlib
import hmac
import json
import os
import ssl
import uuid
from datetime import datetime
from time import mktime
from typing import Dict, List, Any
from urllib.parse import urlencode
from urllib.parse import urlparse
from wsgiref.handlers import format_date_time

import requests
import websocket


class IFlySparkAgentClient(object):
    """
        任务链客户端,用于通过API调用任务链进行会话
    """

    # 初始化
    def __init__(self,
                 base_url: str = os.getenv("IFLY_SPARK_AGENT_BASE_URL"),
                 app_id: str = os.getenv("IFLY_SPARK_AGENT_APP_ID"),
                 app_secret: str = os.getenv("IFLY_SPARK_AGENT_APP_SECRET"),
                 ):
        if not base_url:
            raise ValueError("IFLY_SPARK_AGENT_BASE_URL is not set")
        if not app_id:
            raise ValueError("IFLY_SPARK_AGENT_APP_ID is not set")
        if not app_secret:
            raise ValueError("IFLY_SPARK_AGENT_APP_SECRET is not set")

        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url
        self.host = urlparse(self.base_url).hostname
        # chat会话接口地址
        self.chat_endpoint = "/openapi/flames/api/v2/chat"
        # 文件上传接口地址
        self.upload_endpoint = "/openapi/flames/file/v2/upload"
        # 工具调用地址
        self.tool_debug_endpoint = "/openapi/flames/api/v1/skill-tool/tool-debug"
        # 获取智能体信息接口地址
        self.get_process_endpoint = f"/openapi/flames/api/v2/apps/{app_id}/resources"

        # 生成url,拼接API网关核心鉴权签名信息
        self.agents=self.get_agent_info()
        self.agents.append(
            # add upload_file
            {
                "name": "upload_file",
                "description": "upload file. Format support: image(jpg、png、bmp、jpeg), doc(pdf)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "file path"
                        }
                    },
                    "required": ["file"]
                }
            }
        )
        self.name_idx: Dict[str, int] = {}
        # build name_idx
        for i, agent in enumerate(self.agents):
            self.name_idx[agent["name"]] = i
        # print("########## agent list tools: ", self.agents)
        # print("########## agent name_idx: ", self.name_idx)

    def create_url(self, method, path, wsProtocol, bodyId):
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
            "bodyId": bodyId
        }
        base_url = self.base_url.replace("https", "wss").replace("http", "ws") if wsProtocol else self.base_url
        # 拼接鉴权参数，生成url
        url = base_url + path + '?' + urlencode(v)
        # 此处打印出建立连接时候的url,参考本demo的时候可取消上方打印的注释，比对相同参数时生成的url与自己代码生成的url是否一致
        return url

    # 建立连接, 生成内容
    async def chat_completions(self, agent_info: Dict[str, Any], arguments):
        # print("### chat_completions ### agent_info:", agent_info)
        body_id = agent_info["bodyId"]
        for agent in self.agents:
            if body_id == agent["bodyId"]:
                request_url = self.create_url("GET", self.chat_endpoint, True, body_id)
                # print("### generate ### request_url:", request_url)
                websocket.enableTrace(False)
                ws = websocket.WebSocketApp(
                    request_url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open
                )
                ws.app_id = self.app_id
                ws.body_id = agent_info["bodyId"]
                ws.full_response = ""

                if agent["kindCode"] and agent["kindCode"] == "SKILL_PROCESS":
                    ws.params = {
                        "header": {
                            "traceId": str(uuid.uuid1()).replace("-", ""),
                            "mode": 0,
                            "appId": self.app_id,
                            "bodyId": agent_info["bodyId"]
                        },
                        "payload": {
                            "input": {
                                agent["startNode"]: arguments
                            }
                        }
                    }
                elif agent["kindCode"] and agent["kindCode"] == "SKILL_KNOW":
                    arguments["content_type"] = "text"
                    ws.params = {
                        "header": {
                            "traceId": str(uuid.uuid1()).replace("-", ""),
                            "mode": 0,
                            "appId": self.app_id,
                            "bodyId": agent_info["bodyId"]
                        },
                        "payload": {
                            "text": [
                                arguments
                            ]
                        }
                    }

                ws.run_forever(
                    sslopt={
                        "cert_reqs": ssl.CERT_NONE
                    }
                )
                return ws.full_response
            else:  # 其他智能体
                # print("### other agent, not support")
                pass
        return "other agent, not support"

    def get_agent_info(self) -> List[Dict[str, Any]]:
        """
        get flow info, such as flow description, parameters
        :return:
        """
        url = f"{self.base_url}{self.get_process_endpoint}"
        headers = {
            "Authorization": f"Bearer {self.app_id}:{self.app_secret}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json_arr = response.json()
        json_arr = filter(lambda x: x["kindCode"] == "SKILL_PROCESS" or  x["kindCode"] == "SKILL_TOOL" or x["kindCode"] == "SKILL_KNOW", json_arr)

        return list(map(lambda item: {
            "kindCode": item["kindCode"],
            "bodyId": item["bodyId"],
            "name": item["name"],
            "description": item["description"],
            "startNode": item["startNode"],
            "inputSchema": item["inputSchema"],
            "toolId": item["toolId"] if item.get("toolId") else "",
            "toolboxId": item["toolboxId"] if item.get("toolboxId") else ""
        }, json_arr))

    def tool_debug(self, agent, arguments) -> Any:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.app_id}:{self.app_secret}",
        }
        body = {
            "header": {
                "mode" : 0
            },
            "payload": {
                "bodyId": agent["bodyId"],
                "id": agent["toolId"],
                "args": arguments
            },
            "bodyId": agent["toolboxId"]
        }

        request_url = self.create_url("POST", self.tool_debug_endpoint, False, agent["toolboxId"])
        # print("### upload ### request_url:", request_url)
        response = requests.post(request_url, json=body, headers=headers, verify=False)
        return response.text

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
        request_url = f"{self.base_url}{self.upload_endpoint}"
        # print("### upload ### request_url:", request_url)
        response = requests.post(request_url, json=body, headers=headers, verify=False)
        # print('response:', response.text)
        response_data = json.loads(response.text)
        code = response_data["header"]["code"]
        if code != 0:
            # print(f'请求错误: {code}, {response_data}')
            return None
        else:
            return response_data["payload"]["id"]

    # 收到websocket错误的处理
    def on_error(self, ws, error):
        # print("### on_error:", error)
        try:
            ws.close()
        except Exception as e:
            # # print("### on_close error:", e)
            pass

    # 收到websocket关闭的处理
    def on_close(self, ws, close_status_code, close_msg):
        # print("### on_close ### code:", close_status_code, " msg:", close_msg)
        pass

    # 收到websocket连接建立的处理
    def on_open(self, ws):
        # print("### on_open ###")
        request_params = json.dumps(ws.params)
        # print("### request:", request_params)
        ws.send(request_params)

    # 收到websocket消息的处理
    def on_message(self, ws, message):
        # print("### on_message:", message)
        data = json.loads(message)
        # if data["header"]["status"] == 1:
        if "payload" in data:
            text = ""
            if "output" in data["payload"]:
                if data["header"]["status"] == 1:
                    node_code = data["payload"]["output"]["node"]
                    node_res_payload = data["payload"]["output"]["payload"]
                    # print("### on_message, node_code:", node_code, " node_res_payload:", node_res_payload)
                    text = node_res_payload["text"]
            elif "choices" in data["payload"]:
                if data["header"]["status"] in [0, 1, 2]:
                    choices = data["payload"]["choices"]
                    if choices["text"][0]:
                        text = choices["text"][0]["content"]
            ws.full_response += text

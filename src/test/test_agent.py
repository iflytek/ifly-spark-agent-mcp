from src.mcp_server.agent import IflySparkAgentClient


if __name__ == '__main__':
    baseUrl = "http://172.29.228.145:30009"
    appId = "2A5BB694E04045D38663"
    appSecret = "C365E6CBA5554E6CABAB306543D4A573"
    bodyId = "xzrbcess5odopusaqeh4rfs53cj8yflg"
    spark_agent_client = IflySparkAgentClient(baseUrl, appId, appSecret, bodyId)

    agent_info = {
        "body_id": bodyId
    }
    agent_input = {
        # 开始节点nodeId
        "a221ed90a3": {
            "in": "abc"
        }
    }
    spark_agent_client.chat_completions(agent_info, agent_input)


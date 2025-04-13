from mcp_server.agent import IflySparkAgentClient


if __name__ == '__main__':
    baseUrl = "http://172.31.164.103:30009"
    appId = "9FE168C0D750461FBEFF"
    appSecret = "7CEC56A21DC04A05A2EDCD7A30C89A5D"
    spark_agent_client = IflySparkAgentClient(baseUrl, appId, appSecret)

    bodyId = spark_agent_client.flows[0]["bodyId"]
    startNode = spark_agent_client.flows[0]["startNode"]

    agent_info = {
        "body_id": spark_agent_client.flows[0]["bodyId"]
    }
    agent_input = {
        "userInput": "aaaaaa"
    }
    spark_agent_client.chat_completions(agent_info, agent_input)


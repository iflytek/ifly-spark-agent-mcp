from mcp_server.agent import IFlySparkAgentClient
import asyncio


if __name__ == '__main__':
    baseUrl = "http://172.31.164.103:30009"
    appId = "9FE168C0D750461FBEFF"
    appSecret = "7CEC56A21DC04A05A2EDCD7A30C89A5D"
    spark_agent_client = IFlySparkAgentClient(baseUrl, appId, appSecret)

    bodyId = spark_agent_client.agents[0]["bodyId"]
    startNode = spark_agent_client.agents[0]["startNode"]

    agent_info = {
        "bodyId": spark_agent_client.agents[0]["bodyId"]
    }
    agent_input = {
        "userInput": "aaaaaa"
    }

    result = asyncio.run(spark_agent_client.chat_completions(agent_info, agent_input))
    print(result)

